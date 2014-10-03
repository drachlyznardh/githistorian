# Main module for Git-Historian

from subprocess import check_output
import re

import node
import vertical
import horizontal

import layout as layout

class Historian:
	def __init__ (self):
		self.head = 0
		self.commit = {}
		self.vertical = []
		self.max_column = -1
	
	def get_history(self):
		git_history_dump = check_output(["git", "log", '--pretty="%H %P%d"', "--all"])

		for line in git_history_dump.split('\n'):
			if len(line) == 0: continue

			hashes_n_refs = re.compile(r'''"(.*) \((.*)\)"''').match(line)
			if hashes_n_refs:
				hashes = hashes_n_refs.group(1).split()
				refs = hashes_n_refs.group(2).split(',')
			else:
				hashes = line[1:-1].split()
				refs = ""

			current = node.Node()
			if hashes:
				current.hash = hashes[0]
				for i in hashes[1:]: current.parent.append(i)
			for i in refs: current.ref.append(i.strip())

			if not self.head: self.head = current.hash
			self.commit[current.hash] = current
	
	def unroll_vertically(self, debug):
		
		visit = vertical.Order(self.head)

		while 1:

			target = visit.pop()
			if not target:
				if debug: print "No Target"
				break

			commit = self.commit[target]
			if not commit:
				if debug: print "No Commit"
				break
			if commit.done:
				if debug: print "%s is done, skipping" % commit.hash[:7]
				continue

			if len(commit.child) > 1:
				skip = 0
				for i in reversed(commit.child):
					child = self.commit[i]
					if child and not child.done:
						visit.cpush(i)
						skip = 1
				if skip: continue
			elif len(commit.child) > 0:
				child = self.commit[commit.child[0]]
				if child and not child.done:
					visit.cpush(commit.child[0])
					continue
			
			self.vertical.append(commit.hash)

			if len(commit.parent) > 1:
				for i in commit.parent:
					parent = self.commit[i]
					if parent and not parent.done:
						visit.ppush(i)
			elif len(commit.parent) > 0:
				parent = self.commit[commit.parent[0]]
				if parent and not parent.done:
					visit.push(commit.parent[0])
			
			if debug: visit.show()
			commit.done = 1

	def unroll_horizontally(self, debug):

		reserved = 2
		order = horizontal.Order(reserved, debug)

		# Children must appear in their vertical order
		for name in self.vertical:
			commit = self.commit[name]
			if commit: commit.child = []

		for name in self.vertical:
			commit = self.commit[name]
			if commit: commit.know_your_parents(self.commit)

		for name in self.vertical:
			commit = self.commit[name]
			if commit: commit.know_your_column()

		for name in self.vertical:
			
			if debug: order.show()
			commit = self.commit[name]
			if not commit:
				if debug:
					print "No Commit for name %s" % name[:7]
				break

			if commit.static:
				if debug:
					print "%s has fixed column %d" % (
					commit.hash[:7], commit .column)
				order.static_insert(commit)

			for child in commit.child[1:]:
				if debug:
					print "  Should be archiving branch for %s" % child[:7]
				order.archive(name, child)

			for parent in commit.parent:
				if debug:
					print "  Inserting (%s, %s)" % (
					name[:7], parent[:7])
				order.insert(commit, self.commit[parent])

		for index in range(len(order.l)):
			for name in order.l[index].l:
				if debug:
					print "Calling %s with %d from column" % (
					name[:7], index)
				target = self.commit[name]
				if target and target.column == -1:
					target.column = index

		for i in reversed(range(len(order.archived))):
			column = order.archived[i]
			index = column.index
			for name in column.l:
				if debug:
					print "Calling %s with %d from archive" % (
					name[:7], index)
				target = self.commit[name]
				if target and target.column == -1:
					target.column = index
		
		self.max_column = len(order.l)

	def print_graph (self, debug):
		
		head = self.commit[self.head]
		if not head:
			print "Wut!"
			return

		t = layout.Layout(self.max_column, self.commit)

		for name in self.vertical:

			commit = self.commit[name]
			if not commit:
				print "No Commit for name %s" % name[:7]
				break

			if debug: print "\nP %s" % name[:7]
			
			t.swap()

			t.bottom[commit.column] = ''
			for name in commit.parent:
				parent = self.commit[name]
				if not parent:
					print "No parent with name %s" % name[:7]
				t.bottom[parent.column] = name

			if debug: t.plot_top()
			if debug: t.plot_bottom()
			print "%s %s" % (t.draw_layout(commit), commit.to_oneline())
			
	def tell_the_story(self, debug=0):

		if not self.commit:
			self.get_history()

		for i in self.commit:
			self.commit[i].know_your_parents(self.commit)
	
		self.unroll_vertically(debug)
		self.unroll_horizontally(debug)
		self.print_graph(debug)
