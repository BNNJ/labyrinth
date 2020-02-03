#!/usr/bin/env python

import platform
import os

# curses n'est pas installe de base sur windows, je propose donc de le faire ici
try:
	import curses
except ImportError:
	print('Le module curses n\'est pas installe sur votre machine.')
	print('Ce module est necessaire a ce programme, il permet de manipuler')
	print('le terminal. Voulez vous l\'installer ?')
	print('"Y" puis entree pour l\'installer,')
	print('n\'importe quelle autre touche pour quitter')
	print('---------------------')
	print('The curses module is not installed on your machine.')
	print('I used it for this program, it allows terminal handling')
	print('Do you want to install it ?')
	print('"Y" then press Enter to install, any other key to quit')
	if input().lower() == 'y':
		import subprocess
		import sys
		modname = 'windows-curses'
		subprocess.check_call([sys.executable, '-m', 'pip', 'install', modname])
	else:
		exit(0)

################################## README ! ####################################
# This uses curses to interact with the terminal
# curses is not complicated, but might be confusing at first,
# so here are some basics :
#
# curses.newwin(h, w, y, x)
#	creates a new window of size h * w at position y, x
# win.addstr(y, x, str. attr)
#	add the string 'str' to the window 'win' at position y, x, with
#	the attribute 'attr'.
#	it DOES NOT display the string yet, instead it waits for a refresh of
#	the window to display every changes made to that window
# win.getch()
#	captures user input, one key at a time, after refreshing the window
# win.noutrefresh()
#	stages changes to the window to be displayed on next doupdate() call
# curses.doupdate()
#	applies all changes staged with noutrefresh()
# win.refresh()
#	calls win.noutrefresh() and then curses.doupdate()
# curses.wrapper(function)
#	handles the basic initialisation of curses and calls 'function',
#	then tears everything down. It's basically a wrapper around a
#	try/except/finally block.
#
# curses also defines some 'constants', for example to simplify user input
# recognition, or attributes in addstr.
################################################################################

# curses defines KEY_ENTER as only 343 (the enter key at the bottom right
# of the keyboard). So I define a new one that comprises both enter keys,
# as well as carriage return ('\r', or 13) just in case weird things
# happen with Windows
KEY_ENTER = [10, 13, 343]

### some globals to adapt the display to the size of the terminal ###
# size of the terminal
TERM_H, TERM_W = 0, 0
# size of the maze in hard mode
HEIGHT, WIDTH = 7, 11

# unicode for arrows symbols
ARROW_LEFT = 8592
ARROW_UP = 8593
ARROW_RIGHT = 8594
ARROW_DOWN = 8595
ARROWS = (ARROW_RIGHT, ARROW_UP, ARROW_LEFT, ARROW_DOWN)

# read a maze from a file, and return it as a 2D array
def readMap(file):
	with open(file) as f:
		maze = f.read().split('\n')
	return maze

# returns the coordinates of the start and exit cells
def startEnd(maze):
	sx, sy, ex, ey = 0, 0, 0, 0
	for i, line in enumerate(maze):
		if 'S' in line:
			sx = line.find('S')
			sy = i;
		if 'E' in line:
			ex = line.find('E')
			ey = i
	return (sy, sx, ey, ex)

def winPosition(h, w):
	y, x = TERM_H // 2 - h // 2, TERM_W // 2 - w // 2
	return (y, x)

# handles the display for the hard mode
# The player's position is always in the center of the displayed part
# of the maze, which means an offset is required to handle
# the cases where the player is close to the border of the maze.
# that is also why the window must be cleared first, as some parts
# of it might not be rewritten.
# concerning the display itself, it is done by using only a slice of the
# maze array, and then slices of each lines. The boundaries of those slices
# are calculated and stored in min/max _y/x.
# The positioning is based on the offset, which again is necessary
# when the player is close to the edge of the maze
def displayHardMode(maze_win, maze, y, x):
	maze_win.clear()
	h, w = len(maze), len(maze[0])
	min_y, max_y = y - (HEIGHT) // 2, y + (HEIGHT + 1) // 2
	min_x, max_x = x - (WIDTH) // 2, x + (WIDTH + 1) // 2
	offset_y = max(-min_y, 0) + 1
	offset_x = max(-min_x, 0) + 1
	min_y, max_y = max(min_y, 0), min(max_y, h)
	min_x, max_x = max(min_x, 0), min(max_x, w)
	for i, v in enumerate(maze[min_y:max_y]):
		maze_win.addstr(i + offset_y, offset_x, v[min_x:max_x])
	maze_win.addch((HEIGHT + 1) // 2, (WIDTH + 1) // 2, ' ', curses.A_REVERSE)
	maze_win.refresh()

#
def displayEasyMode(maze_win, maze):
	for i, line in enumerate(maze):
		maze_win.addstr(i, 0, line)
	maze_win.refresh()

# mapping of the modifications to x and y depending on the move direction
directions = {
	curses.KEY_LEFT:	(0, -1),
	curses.KEY_RIGHT:	(0, 1),
	curses.KEY_UP:		(-1, 0),
	curses.KEY_DOWN:	(1, 0)
}

# applies the position modifications to y and x, checks if the new
# position is legal, then returns the coordinates of the player. 
def move(maze, y, x, direction):
	new_y = y + directions[direction][0]
	new_x = x + directions[direction][1]
	if new_x >= len(maze[0]) and new_y >= len(maze):
		return (y, x)
	if maze[new_y][new_x] != '#':
		return (new_y, new_x)
	return (y, x)

# a simple popup function: creates a new window in the center
# of the screen, displays a message until a key is pressed,
# then closes and deletes the window.
def popup(msg):
	if msg == '':
		return
	info_txt = 'press any key to continue'
	msg = msg.split('\n')
	h, w = len(msg), len(info_txt)
	for line in msg:
		w = max(w, len(line))
	y, x = winPosition(h, w)
	win = curses.newwin(h + 4, w + 4, y, x)
	win.border()
	for i, line in enumerate(msg):
		win.addstr(i + 1, w // 2 - len(line) // 2 + 2, line)
	win.addstr(h + 2, w // 2 - (len(info_txt) // 2) + 2, info_txt)
	win.getch()
	win.clear()
	win.refresh()
	del win

# handle the resizing of the terminal by fetching the new dimensions
# and adapting the position of the different UI elements
def resizeTerm(stdscr, win):
	win.clear()
	win.noutrefresh()
	global TERM_H, TERM_W
	h, w = win.getmaxyx()
	TERM_H, TERM_W = stdscr.getmaxyx()
	win.mvwin(TERM_H // 2 - h // 2, TERM_W // 2 - w // 2)

#
def play(stdscr, maze, display_function):
	sy, sx, ey, ex = startEnd(maze)
	player_y, player_x = sy, sx
	y, x = winPosition(HEIGHT, WIDTH)

	maze_win = curses.newwin(HEIGHT + 2, WIDTH + 2, y, x)
	maze_win.keypad(1)

	border = curses.newwin(HEIGHT + 4, WIDTH + 4, y - 1, x - 1)
	border.box()
	border.refresh()

	info_win = curses.newwin(4, WIDTH + 4, y + HEIGHT + 3, x)
	info_win.addstr(0, 0, 'move: %c %c %c %c' %(ARROWS))
	info_win.addstr(1, 0, 'quit: Q')
	info_win.refresh()

	display_function(maze_win, maze, player_y, player_x)
	while True:
		maze_win.refresh()
		ch = maze_win.getch()
		if ch == ord('q'):
			break
		elif ch in directions:
			player_y, player_x = move(maze, player_y, player_x, ch)
			display_function(maze_win, maze, player_y, player_x)
			if player_y == ey and player_x == ex:
				popup('You Won !')
				break
		elif ch == curses.KEY_RESIZE:
			resizeTerm(stdscr, border)
			border.box()
			border.noutrefresh()
			resizeTerm(stdscr, maze_win)
			display_function(maze_win, maze, player_y, player_x)
			curses.doupdate()
	maze_win.clear()
	maze_win.noutrefresh()
	border.clear()
	border.noutrefresh()
	info_win.clear()
	info_win.noutrefresh()
	curses.doupdate()
	del maze_win
	del border

def selectMap():
	_, _, files = next(os.walk(u'./maps'))

	i = 0
	popup('Left and right arrows to cycle through maps\nenter to select')
	while True:
		maze = readMap('./maps/' + files[i])
		h, w = len(maze), len(maze[0])
		y, x = winPosition(h, w)
		win = curses.newwin(h + 2, w + 2, y, x)
		win.keypad(1)
		displayEasyMode(win, maze)
		win.refresh()
		ch = win.getch()
		win.clear()
		win.refresh()
		del win
		if ch == curses.KEY_RIGHT:
			i = min(i + 1, len(files) - 1)
		elif ch == curses.KEY_LEFT:
			i = max(i - 1, 0)
		elif ch in KEY_ENTER:
			return maze

def menu(stdscr, options):
	h, w = len(options), 0
	for v in options:
		w = max(w, len(v))
	w += 2
	y, x = winPosition(h, w)
	win = curses.newwin(h, w, y, x)
	win.keypad(1)
	for i, v in enumerate(options):
		win.addstr(i, 1, v)
	selected = 0
	while True:
		win.chgat(selected, 0, w, curses.A_REVERSE)
		ch = win.getch()
		win.chgat(selected, 0, w, curses.A_NORMAL)
		if ch == curses.KEY_DOWN and selected < h - 1:
			selected += 1
		elif ch == curses.KEY_UP and selected > 0:
			selected -= 1
		elif ch in KEY_ENTER:
			win.clear()
			win.refresh()
			del win
			return selected
		elif ch == curses.KEY_RESIZE:
			resizeTerm(stdscr, win)
			for i, v in enumerate(options):
				try:
					win.addstr(i, 1, v)
				except:
					pass

# we need a function to pass to the curses wrapper, why not a main ?
def main(stdscr):
	global TERM_H, TERM_W
	TERM_H, TERM_W = stdscr.getmaxyx()
	if TERM_H > 24 and TERM_W > 16:
		curses.curs_set(0)
		maze = readMap('maps/map1')
		options = ['play', 'select map', 'game mode', 'quit']
		while True:
			selected = menu(stdscr, options)
			if selected == 0:
				play(stdscr, maze, displayHardMode)
			elif selected == 1:
				maze = selectMap()
			elif selected == 3:
				return
		curses.curs_set(1)
	else:
		stdscr.addstr(0, 0, 'Your terminal is too small for this !')
		stdscr.getch()

# The wrapper function handles the initialization of curses
# calls the function passed as argument in a 'try' block,
# then reverts all changes made to the terminal mode
# and frees the memory allocated in a 'finally' block
curses.wrapper(main)