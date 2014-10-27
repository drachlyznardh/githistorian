# Main module for Git-Historian
# -*- encoding: utf-8 -*-

import sys
import getopt

import hunter
import order

import layout

VERSION="0.0-c"

class Option:

	def __init__ (self):

		self.verbose = 0
		self.debug = 0
		self.all_debug = 0

		self.all_heads = 0
		self.head = []

	def print_version(self):
		print "Git-Historian %s (C) 2014 Ivan Simonini" % VERSION

	def print_help(self):
		print "Usage: %s [options] heads…" % sys.argv[0]
		print
		print ' -D, --all-debug : print all kinds of debug messages'
		print ' -d N, --debug N : add N to the debug counter'
		print
		print 'debug  1 : show heads'
		print 'debug  2 : show data loading'
		print 'debug  4 : show bindings'
		print 'debug  8 : show vertical unroll'
		print 'debug 16 : show column assignments'
		print 'debug 32 : show layout construction'

	def parse (self):

		try:
			optlist, args = getopt.gnu_getopt(sys.argv[1:], 'ahvDd:',
				['help', 'verbose', 'version',
				'all', 'all-heads',
				'debug', 'all-debug'])
		except getopt.GetoptError as err:
			print str(err)
			self.print_help()
			sys.exit(2)

		for key, value in optlist:
			if key in ('-h', '--help'):
				self.print_help()
				sys.exit(0)
			elif key in ('-v', '--verbose'):
				self.verbose = 1
			elif key in ('-a', '--all', '--all-heads'):
				self.all_heads = 1
			elif key in ('-D', '--all-debug'):
				self.all_debug = 1
			elif key in ('-d', '--debug'):
				self.debug += int(value)
			elif key == '--version':
				self.print_version()
				sys.exit(0)

		self.args = args
	
	def d (self, value):
		return self.all_debug or self.debug / value % 2

class Historian:

	def __init__ (self):

		self.verbose = 0

		self.head = []
		self.node = {}

		self.first = None
		self.width = -1

		self.o = Option()
		self.o.parse()

	def update_width (self, value):
		self.width = max(self.width, value)

	def skip_if_done (self, names):
		result = []
		for name in names:
			if not self.node[name].done:
				result.append(name)
		return result

	def only_if_has_column (self, names):
		result = []
		for name in names:
			if self.node[name].has_column():
				result.append(name)
		return result

	def clear (self):
		for commit in self.node.values():
			commit.done = 0

	def bind_children (self, debug):

		if debug: print '-- Binding Children --'

		visit = order.LeftmostFirst()
		visit.push(self.head)

		while visit.has_more():

			name = visit.pop()
			commit = self.node[name]

			if debug: print '  Visiting %s' % name[:7]

			if commit.done:
				if debug: print '  %s is done, skipping…' % name[:7]
				continue

			for i in commit.parent:
				self.node[i].add_child(name)

			visit.push(self.skip_if_done(commit.parent))

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
			target = self.node[name]

			if debug:
				print 'Visiting %s %s' % (name[:7], visit.show())

			# Even if done, a node can drop down in the chain after its
			# last-calling child
			if target.done:

				# No need to drop down beyond the last element
				if previous == target.hash: continue

				# Binding top and bottom nodes together
				self.node[target.top].bottom = target.bottom
				self.node[target.bottom].top = target.top

				# Binding previous and current nodes together
				target.top = previous
				self.node[previous].bottom = name

				# Bumping the row number another time
				row += 1
				target.row = row

				# This node is now the last
				target.bottom = None

				# Recording current node as the next previous
				previous = name
				continue

			# No node can appear before any of its children
			children = self.skip_if_done(target.child)
			if len(children): continue

			# Bind this node with the previous, if any, or…
			if previous:
				target.top = previous
				self.node[previous].bottom = name

			# … record this node as the first in the chain
			else: self.first = name

			# Bumping the row number
			row += 1
			target.row = row

			# Add parents to the visit
			visit.push(self.skip_if_done(target.parent))

			# The current node is the next previous
			previous = name

			# The current node is done
			target.done = 1

	def find_column_for_head (self, name, debug):

		if debug: print '%s has to find its own column!!!' % name [:7]
		target = self.node[name]

		# We do not consider parents which have no column yet, those will be
		# called in a later step
		parents = self.only_if_has_column(target.parent)
		parent_no = len(parents)
		if debug: print '%s has %d parents with column, (%s)' % (name[:7],
			len(parents), ', '.join([e[:7] for e in parents]))

		# If no parent has a column yet, a whole new column is selected
		if parent_no == 0:
			self.width += 1
			target.set_column(self.width)
			self.update_width(self.width)
			return

		rightmost = sorted(parents,
			key=lambda e: self.node[e].border, reverse=True)[0]

		if parent_no == len(target.parent):
			target.set_column(self.node[rightmost].column)
		else:
			target.set_column(1 + self.node[rightmost].column)

		self.update_width(target.column)
		return

		# Should I take the column of the rightmost parent, only when ALL the
		# parents are out there already?

		# If there is only one selected parent, and that is the only parent, the
		# target node can appear on top of it
		if parent_no == len(target.parent):
		#if parent_no == 1 and len(target.parent) == 1:
			target.set_column(self.node[parents[0]].column)
			return

		# Selecting the two parents with the lowest row and the rightmost
		# column
		lowest = sorted(parents,
			key=lambda e: self.node[e].row, reverse=True)[0]
		rightmost = sorted(parents,
			key=lambda e: self.node[e].border, reverse=True)[0]
		if debug: print 'Lowest (%s), Rightmost (%s)' % (lowest[:7], rightmost[:7])

		# If they are same node…
		if lowest == rightmost:

			# … we must also verify if that node is the only one on that
			# column
			count = 0
			value = self.node[rightmost].border
			for e in parents:
				if self.node[e].border == value:
					count += 1

			if debug: print 'Count is %d' % count

			# If that node is lonely, the target can be put on top of it
			if count == 1:
				target.set_column(self.node[lowest].column)

			# If there are more than one node on the rightmost column, the
			# arrow must appear on the next one, so the target node shifts
			# one more step on the right
			else:
				target.set_column(1 + self.node[rightmost].border)
				self.update_width(target.column)

		# If the rightmost parent is not the lowest, an arrow would cross
		# it. The target node must be put on the next column
		else:
			target.set_column(1 + self.node[rightmost].border)
			self.update_width(target.column)

	def find_column_for_parents (self, name, debug):

		target = self.node[name]
		column = target.column

		# Parents are processed in row order, from lower to upper
		for e in sorted(target.parent,
				key=lambda e: self.node[e].row, reverse=True):
			parent = self.node[e]

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
				if debug: print 'From %s, Up to %s' % (e[:7], upper[:7])
				if upper == name: break
				upper = self.node[upper]
				if upper.has_column() and upper.column <= column:
					column = max(column, upper.column + 1)
				upper = upper.top

			# The parent column is set, as well as the caller's border
			parent.set_column(column)
			parent.set_border(target.column)

			# The graph's width is updated. The first available column is the
			# next one
			self.update_width(column)
			column += 1

	def column_unroll (self, debug):

		if debug: print '-- Column Unroll --'

		self.width = -1

		# The visit starts for the named heads
		visit = order.ColumnOrder()
		visit.push(self.head)

		while visit.has_more():

			name = visit.pop()
			target = self.node[name]
			
			# No node is processed more than once
			if target.done: continue

			if debug: print '  Visiting %s' % name[:7]

			# If a node is a named head and has not yet a column assigned, it
			# must look for a valid column on its own
			if target.hash in self.head and not target.has_column():

				self.find_column_for_head (name, debug)

			# The node assigns a column to each of its parents, in order,
			# ensuring each starts off on a valid position
			self.find_column_for_parents (name, debug)

			# Parents are added to the visit, then the node is done
			visit.push(self.skip_if_done(target.parent))
			target.done = 1

	def print_graph (self, debug):
		
		if debug: print '-- Print Graph --'

		t = layout.Layout(self.width + 1, self.node, debug)
		h = hunter.MessageHunter()

		name = self.first

		while name:

			commit = self.node[name]
			if not commit:
				print "No Commit for name %s" % name[:7]
				break

			if debug: print "\nP %s" % name[:7]
			
			t.compute_layout(commit)

			message = h.describe(name)

			print '%s\x1b[m %s' % (t.draw_transition(), message[0])
			for i in message[1:-1]:
				print '%s\x1b[m %s' % (t.draw_padding(), i)

			name = commit.bottom

	def tell_the_story(self):

		self.head = hunter.HeadHunter(self.o, self.o.d(1)).hunt()
		self.node = hunter.HistoryHunter(self.head, self.o.d(2)).hunt()

		self.bind_children(self.o.d(4))
		self.clear()
		self.row_unroll(self.o.d(8))
		self.clear()
		self.column_unroll(self.o.d(16))
		self.print_graph(self.o.d(32))

		return

