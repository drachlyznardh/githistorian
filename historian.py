# Main module for Git-Historian
# -*- encoding: utf-8 -*-

import option
import hunter
import order

import layout

VERSION="0.0-c"

import bintrees

class Grid:

	def __init__ (self):
		self.store = {}

	def at (self, index):
		try:
			return self.store[index]
		except:
			self.store[index] = bintrees.RBTree()
			return self.store[index]

	def add (self, node):

		t = self.at(node.column)
		t.insert(node.column, node.name)
		return

	def upper (self, column):
		try:
			key, value = self.store.prev_item(column)
			return value
		except KeyError: return None

	def lower (self, column):
		try:
			key, value = self.store.succ_item(column)
			return value
		except KeyError: return None

class Historian:

	def __init__ (self):

		self.verbose = 0

		self.head = []
		self.db = None

		self.first = None
		self.width = -1

		self.o = option.Option()
		self.o.parse()

	def update_width (self, value):
		self.width = max(self.width, value)

	def bind_children (self, debug):

		if debug: print '-- Binding Children --'

		visit = order.LeftmostFirst()
		visit.push(self.head)

		while visit.has_more():

			name = visit.pop()
			commit = self.db.at(name)

			if debug: print '  Visiting %s' % name[:7]

			if commit.done:
				if debug: print '  %s is done, skipping…' % name[:7]
				continue

			for i in commit.parent:
				self.db.at(i).add_child(name)

			visit.push(self.db.skip_if_done(commit.parent))

			commit.done = 1

	def row_unroll (self, debug):

		if debug: print '-- Row Unroll --'

		# Visit starts with all the heads
		visit = order.RowOrder()
		visit.push(self.head)

		# Reference to previous node, to build the chain
		previous = None

		# Starting over the first row
		row = -1

		while visit.has_more():

			name = visit.pop()
			target = self.db.at(name)

			if debug:
				print 'Visiting %s %s' % (name[:7], visit.show())

			# Even if done, a node can drop down in the chain after its
			# last-calling child
			if target.done:

				# No need to drop down beyond the last element
				if previous == target.name: continue

				# Binding top and bottom nodes together
				self.db.at(target.top).bottom = target.bottom
				self.db.at(target.bottom).top = target.top

				# Binding previous and current nodes together
				target.top = previous
				self.db.at(previous).bottom = name

				# Bumping the row number another time
				row += 1
				target.row = row

				# This node is now the last
				target.bottom = None

				# Recording current node as the next previous
				previous = name
				continue

			# No node can appear before any of its children
			children = self.db.skip_if_done(target.child)
			if len(children): continue

			# Bind this node with the previous, if any, or…
			if previous:
				target.top = previous
				self.db.at(previous).bottom = name

			# … record this node as the first in the chain
			else: self.first = name

			# Bumping the row number
			row += 1
			target.row = row

			# Add parents to the visit
			visit.push(self.db.skip_if_done(target.parent))

			# The current node is the next previous
			previous = name

			# The current node is done
			target.done = 1

	def find_column_for_head (self, name, debug):

		if debug: print '%s has to find its own column!!!' % name [:7]
		target = self.db.at(name)

		# We do not consider parents which have no column yet, those will be
		# called in a later step
		assigned, missing = self.db.split_assigned_from_missing(target.parent)

		if debug: print '%s has %d parents with column, (%s)' % (name[:7],
			len(assigned), ', '.join([e[:7] for e in assigned]))
		if debug: print '%s has %d parents without column, (%s)' % (name[:7],
			len(missing), ', '.join([e[:7] for e in missing]))

		# If no parent has a column yet, a whole new column is selected
		if len(assigned) == 0:
			self.width += 1
			return self.width

		# Selecting the parent node with the rightmost column
		rightmost = sorted(assigned,
			key=lambda e: self.db.at(e).border, reverse=True)[0]
		column = self.db.at(rightmost).border

		# This head should also appear on the right of previous heads
		index = self.head.index(name)
		previous = self.head[index - 1]
		if debug: print 'This(%s) Previous(%s)' % (name, previous)
		column = max(column, self.db.at(previous).column)
		if debug: print 'Porca puttana!!! %d' % column

		# If all the parents were already assigned, the target can sit above the
		# rightmost column
		if len(missing) == 0:

			if len(target.parent) == 1: return column

			assigned.sort(key=lambda e: self.db.at(e).border, reverse=True)
			lowest = sorted(assigned, key=lambda e:self.db.at(e).row, reverse=True)[0]

			first = self.db.at(assigned[0])
			second = self.db.at(assigned[1])

			if first.column == second.column: return 1 + column

			if first.name != lowest: return 1 + column

			return column

		assigned.sort(key=lambda e: self.db.at(e).row, reverse=True)
		missing.sort(key=lambda e: self.db.at(e).row, reverse=False)

		if self.db.at(assigned[0]).row < self.db.at(missing[0]).row:
			return 1 + column

		# Still, between the highest parent and the target there could be some
		# other node taking the border column for itself
		upper = self.db.at(missing[0]).top
		while upper:
			if debug: print 'From %s, up to %s' % (name[:7], upper[:7])
			if upper == name: break
			upper = self.db.at(upper)
			if upper.has_column() and upper.column <= column:
				column = max(column, upper.column + 1)
			upper = upper.top

		return column

	def find_column_for_parents (self, name, grid, debug):

		target = self.db.at(name)
		column = target.column

		# Parents are processed in row order, from lower to upper
		for e in sorted(target.parent,
				key=lambda e: self.db.at(e).row, reverse=True):
			parent = self.db.at(e)

			# If a parent has already a column, the column next to its marks the
			# leftmost spot for the following parents, as the border for the
			# target node
			if parent.has_column():
				parent.set_border(target.column)
				column = parent.border + 1
				if debug: print 'Pushing column beyond %s\'s border %d' % (e[:7], parent.border)
				continue

			# Starting from the node atop of the current, the graph is
			# traversed until the caller is found. The rightmost column
			# encountered in the process is the boundary for this node's column
			upper = parent.top
			while upper:
				if debug: print 'Higher, from %s to %s' % (e[:7], upper[:7])
				if upper in parent.child:
					upper = self.db.at(upper).top
					continue
				upper = self.db.at(upper)
				if upper.has_column() and upper.column == column:
					if len(upper.parent) == 0:
						upper = upper.top
						continue
					lowest = sorted([self.db.at(e).row for e in upper.parent])[-1]
					if lowest > parent.row:
						if debug: print '  Aligned node %s has lower parents' % upper.name[:7]
						column = max(column, upper.border + 1)
						break
				upper = upper.top

			lower = parent.bottom
			while lower:
				if lower in parent.parent:
					lower = self.db.at(lower).bottom
					continue
				lower = self.db.at(lower)
				if lower.has_column() and lower.column == column:
					if len(lower.child) == 0:
						lower = lower.bottom
						continue
					highest = sorted([self.db.at(e).row for e in lower.child])[-1]
					if highest < parent.row:
						column = max(column, lower.border + 1)
						break
				lower = lower.bottom

			upward = 1
			downward = 0
			while upward and downward:

				lower = grid.lower(column)
				if lower:
					lower = self.db.at(lower)
					highest = sorted([self.db.at(e).row for e in lower.child])[0]

					if highest < parent.row:
						column = max(column, lower.border + 1)
						downward = 0
						continue
					else:
						upward = 1
						downward = 1
				else: downward = 0

				upper = grid.upper(column)
				if upper:
					upper = self.db.at(upper)
					lowest = sorted([self.db.at(e).row for e in upper.parent])[-1]
					if lowest > parent.row:
						print 'Aligned node (%s) has no lower parents' % upper.name[:7]
						column = max(column, upper.border + 1)
						upward = 0
						continue
					else:
						upward = 1
						downward = 1
				else: upward = 0

			parent.set_column(column)
			parent.set_border(target.column)
			grid.add(parent)

			# The graph's width is updated. The first available column is the
			# next one
			self.update_width(column)
			column += 1

	def column_unroll (self, debug):

		if debug: print '-- Column Unroll --'

		self.width = -1
		grid = Grid()

		# The visit starts for the named heads
		visit = order.ColumnOrder()
		visit.push(self.head)

		while visit.has_more():

			name = visit.pop()
			target = self.db.at(name)
			
			# No node is processed more than once
			if target.done: continue

			if debug: print '  Visiting %s' % name[:7]

			# If a node is a named head and has not yet a column assigned, it
			# must look for a valid column on its own
			if target.name in self.head and not target.has_column():

				column = self.find_column_for_head (name, debug)
				target.set_column(column)
				self.update_width(column)
				grid.add(target)

			# The node assigns a column to each of its parents, in order,
			# ensuring each starts off on a valid position
			self.find_column_for_parents (name, grid, debug)

			# Parents are added to the visit, then the node is done
			visit.push(self.db.skip_if_done(target.parent))
			target.done = 1

			#print
			#self.print_graph(0)

	def print_graph (self, debug):
		
		if debug: print '-- Print Graph --'

		t = layout.Layout(self.width + 1, self.db, debug)
		h = hunter.MessageHunter()

		name = self.first

		while name:

			node = self.db.at(name)
			if not node:
				print "No Commit for name %s" % name[:7]
				break

			if debug: print "\nP %s" % name[:7]
			
			t.compute_layout(node)

			message = h.describe(name)

			try:
				print '%s\x1b[m %s' % (t.draw_transition(), message[0])
				for i in message[1:-1]:
					print '%s\x1b[m %s' % (t.draw_padding(), i)
			except IOError as error: return

			name = node.bottom

	def tell_the_story(self):

		self.head = hunter.HeadHunter(self.o, self.o.d(1)).hunt()
		self.db = hunter.HistoryHunter(self.head, self.o.d(2)).hunt()

		self.bind_children(self.o.d(4))
		self.db.clear()
		self.row_unroll(self.o.d(8))
		self.db.clear()
		self.column_unroll(self.o.d(16))
		self.print_graph(self.o.d(32))

		return

