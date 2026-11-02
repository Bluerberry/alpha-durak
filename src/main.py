
from __future__ import annotations

import time
import threading

from dataclasses import dataclass
from typing import Iterable

#            A...K...Q...J...T...9...8...7...6...5...4...3...2...
SPADES   = 0b0001000100010001000100010001000100010001000100010001
HEARTS   = 0b0010001000100010001000100010001000100010001000100010
CLUBS    = 0b0100010001000100010001000100010001000100010001000100
DIAMONDS = 0b1000100010001000100010001000100010001000100010001000


# ---------------------------> Utility

class Spinner:
	__thread: threading.Thread
	__run: threading.Event

	def __init__(self) -> None:
		self.__run = threading.Event()

	def __callback(self, text: str, speed: float):
		spinner = '/', '-', '\\', '|'
		state = 0

		try:
			print('\033[?25l', end="")
			while self.__run.is_set():
				print(f'{spinner[state]} {text}', end='\r', flush=True)
				state = (state + 1) % len(spinner)
				time.sleep(1 / speed)

			print(' ' * (2 + len(text)), end='\r', flush=True)

		except:
			print('\033[?25h', end="")

	def start(self, text: str, speed: float):
		if self.__run.is_set():
			self.stop()

		self.__thread = threading.Thread(
			target=self.__callback,
			args=(text, speed),
			daemon=True
		)

		self.__run.set()
		self.__thread.start()

	def stop(self):
		if not self.__run.is_set():
			return

		self.__run.clear()
		self.__thread.join()

class Cards:

	@staticmethod
	def fromText(text: str) -> int:
		mask = 0b0

		for part in text.upper().split():
			value = [ '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A' ].index(part[:-1])
			suit = [ 'S', 'H', 'C', 'D' ].index(part[-1])
			mask |= 0b1 << (4 * value + suit)

		return mask

	@staticmethod
	def fromMask(mask: int) -> str:
		parts = list[str]()

		for card in Binary.bits(mask):
			n = card.bit_length() - 1
			value = [ '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A' ][n // 4]
			suit = [ 'S', 'H', 'C', 'D' ][n % 4]
			parts.append(value + suit)

		return ' '.join(parts)

class Binary:

	@staticmethod
	def bits(mask: int) -> Iterable[int]:
		while mask:
			bit = 0b1 << (mask.bit_length() - 1)
			mask ^= bit
			yield bit

	@staticmethod
	def submasks(mask: int, max_bits: int) -> Iterable[int]:
		submask = mask
		while submask:
			if submask.bit_count() <= max_bits:
				yield submask

			submask = (submask - 1) & mask

@dataclass(slots=True, frozen=True)
class Gamestate:
	attack: int
	resolved: int
	attacker: int
	defender: int

	def deduceEvent(self, future: Gamestate) -> str:
		if not self.attack:
			if not self.resolved:
				return 'Attack with ' + Cards.fromMask(future.attack)

			if future.attack:
				return 'Continue attack with ' + Cards.fromMask(future.attack)

			return 'Pass the turn'

		if not future.attack:
			if not future.resolved:
				return 'Concede combat'

			defence = self.defender ^ future.defender
			return 'Defend with ' + Cards.fromMask(defence)

		deflect = self.attack ^ future.attack
		return 'Deflect with ' + Cards.fromMask(deflect)

	def generateFutures(self, combat_masks: dict[int, int]):
		if not self.attacker or not self.defender:
			return

		if not self.attack:
			if not self.resolved:

				# First attack
				for attack in self.__generateFirstAttacks():
					yield Gamestate(
						attack,
						0b0,
						self.attacker ^ attack,
						self.defender
					)

				return

			# Pass
			yield Gamestate(
				0b0,
				0b0,
				self.defender,
				self.attacker
			)

			# Second attack
			for attack in self.__generateSecondAttacks():
				yield Gamestate(
					attack,
					self.resolved,
					self.attacker ^ attack,
					self.defender
				)

			return

		if not self.resolved:

			# Deflect
			for deflect in self.__generateDeflects():
				yield Gamestate(
					self.attack | deflect,
					0b0,
					self.defender ^ deflect,
					self.attacker
				)

		# Concede
		yield Gamestate(
			0b0,
			0b0,
			self.attacker,
			self.defender | self.attack | self.resolved
		)

		# Defend
		for defence in self.__generateDefences(combat_masks):
			yield Gamestate(
				0b0,
				self.resolved | self.attack | defence,
				self.attacker,
				self.defender ^ defence
			)

	def __generateFirstAttacks(self) -> Iterable[int]:
		max_attack_size = self.defender.bit_count()

		# For each value, mask with attacker cards
		for value in range(0, 52, 4):
			available = (self.attacker >> value) & 0b1111

			# For each submask, shift into values and yield
			for attack in Binary.submasks(available, max_attack_size):
				yield attack << value

	def __generateSecondAttacks(self) -> Iterable[int]:

		# Shift all suits into spades to find available values, then mask with attacker cards
		available = self.resolved | self.resolved >> 1 | self.resolved >> 2 | self.resolved >> 3
		available &= SPADES
		available *= 0b1111
		available &= self.attacker

		# Yield each submask
		max_attack_size = self.defender.bit_count()
		yield from Binary.submasks(available, max_attack_size)

	def __generateDeflects(self) -> Iterable[int]:

		# Shift all suits into spades to find available values, then mask with defender cards
		available = self.attack | self.attack >> 1 | self.attack >> 2 | self.attack >> 3
		available &= SPADES
		available *= 0b1111
		available &= self.defender

		# Yield each submask
		max_attack_size = self.attacker.bit_count() - self.attack.bit_count()
		yield from Binary.submasks(available, max_attack_size)

	def __generateDefences(self, combat_masks: dict[int, int]) -> Iterable[int]:
		defences = { 0b0 }
		for attack in Binary.bits(self.attack):
			available = self.defender & combat_masks[attack]

			defences = {
				defence | card
				for defence in defences
				for card in Binary.bits(available & ~defence)
			}

		return defences

class AlphaDurak:
	spoilers: bool

	# Game settings
	__trump: int                    # Trump suit
	__combat_masks: dict[int, int]  # Combat result lookup table

	# Game tree
	__states: list[Gamestate]       # Unique gamestates
	__past_ids: list[int]           # Past gamestate ID's
	__future_ids: list[int]         # Future gamestate ID's
	__past_offsets: list[int]       # State pasts -> pasts[past_offsets[ID] : past_offsets[ID + 1]]
	__future_offsets: list[int]     # State futures -> futures[future_offsets[ID] : future_offsets[ID + 1]]

	# Results
	__depths: list[int]             # Distance from leaf-node
	__labels: list[bool | None]     # True if active player wins

	def __init__(self, trump: int, playerA: str, playerB: str, *, spoilers: bool = True):
		spinner = Spinner()
		spinner.start('Pondering...', 10)

		attacker = Cards.fromText(playerA)
		defender = Cards.fromText(playerB)
		root = Gamestate(0b0, 0b0, attacker, defender)

		self.spoilers = spoilers

		self.__trump = trump
		self.__states = [ root ]

		self.__computeCombatMasks()
		self.__exploreGameTree()
		self.__labelGameTree()

		spinner.stop()

	def __computeCombatMasks(self):
		self.__combat_masks = {}

		for n in range(52):
			suit = [ SPADES, HEARTS, CLUBS, DIAMONDS ][n % 4]
			mask = suit >> (n + 1) << (n + 1)

			if suit != self.__trump:
				mask |= self.__trump

			self.__combat_masks[0b1 << n] = mask

	def __exploreGameTree(self):
		self.__future_ids = []
		self.__future_offsets = [0]

		index = 0
		ids = { self.__states[0]: 0 }

		while index < len(self.__states):
			state = self.__states[index]
			for future in state.generateFutures(self.__combat_masks):
				if future not in ids:
					ids[future] = len(self.__states)
					self.__states.append(future)

				self.__future_ids.append(ids[future])

			self.__future_offsets.append(len(self.__future_ids))
			index += 1

		self.__past_ids = [0] * len(self.__future_ids)
		self.__past_offsets = [0] * len(self.__future_offsets)

		# Find past_offsets by...
		#  1. Counting nr of pasts per state
		#  2. Aggregating to find offsets

		for future in self.__future_ids:
			self.__past_offsets[future + 1] += 1

		for state in range(len(self.__states)):
			self.__past_offsets[state + 1] += self.__past_offsets[state]

		# Find pasts by...
		#  1. Realizing that past states must live between past_offsets[ID] : past_offsets[ID + 1]
		#     Thus we can reuse past_offsets to keep track of the next free index
		#  2. For each future of each state we map pasts[future] to the state,
		#     updating our next free index as we go

		next_index = self.__past_offsets.copy()

		for state in range(len(self.__states)):
			for offset in range(self.__future_offsets[state], self.__future_offsets[state + 1]):
				future = self.__future_ids[offset]
				self.__past_ids[next_index[future]] = state
				next_index[future] += 1

	def __labelGameTree(self):
		self.__depths = [0] * len(self.__states)
		self.__labels = [None] * len(self.__states)

		queue = list[int]()
		unresolved = [0] * len(self.__states)

		for state in range(len(self.__states)):
			unresolved[state] = self.__future_offsets[state + 1] - self.__future_offsets[state]

			if not unresolved[state]:
				self.__labels[state] = False
				queue.append(state)

		index = 0
		while index < len(queue):
			state = queue[index]
			index += 1

			for offset in range(self.__past_offsets[state], self.__past_offsets[state + 1]):
				past = self.__past_ids[offset]

				# Skip if past is already processed
				if self.__labels[past] is not None:
					continue

				# Past player can move into this state and win
				if not self.__labels[state]:
					self.__labels[past] = True

				# Past player loses if they move into this state.
				else:
					unresolved[past] -= 1
					if unresolved[past]:
						continue

					# If past player has no unresolved futures, they lose
					self.__labels[past] = False

				self.__depths[past] = self.__depths[state] + 1
				queue.append(past)

	def __cpuMove(self, state: int):
		label = self.__labels[state]
		wanted = None if label is None else not label

		best_future = None
		best_depth = None

		for offset in range(self.__future_offsets[state], self.__future_offsets[state + 1]):
			future = self.__future_ids[offset]
			if self.__labels[future] != wanted:
				continue

			if label is None:
				return future

			depth = self.__depths[future]
			if best_depth is None or (depth < best_depth if label else depth > best_depth):
				best_future = future
				best_depth = depth

		assert best_future is not None
		return best_future

	def __spoilerTag(self, future: int):
		if self.__labels[future] is None:
			return '(draw)'

		elif self.__labels[future]:
			return f'(L{self.__depths[future]})'

		else:
			return f'(W{self.__depths[future]})'

	def play(self):
		active_player = True
		state = 0

		while self.__depths[state] > 0 or self.__labels[state] is None:
			print('\nPlayer A' if active_player else '\nPlayer B')
			print('  1. CPU move')

			# Print options
			options = 1
			for offset in range(self.__future_offsets[state], self.__future_offsets[state + 1]):
				future = self.__future_ids[offset]
				event = self.__states[state].deduceEvent(self.__states[future])

				options += 1
				prompt = f'  {options}. {event} '
				if self.spoilers:
					prompt += self.__spoilerTag(future)
				print(prompt)

			# Get user input
			while True:
				choice = input('\n > ')
				if not choice.isdigit():
					print('\nInvalid choice')
					continue

				choice = int(choice)
				if choice < 1 or choice > options:
					print('\nInvalid choice')
					continue

				break

			# Get player move
			if choice > 1:
				state = self.__future_ids[self.__future_offsets[state] + choice - 2]
				active_player = not active_player
				continue

			# Get CPU move
			future = self.__cpuMove(state)
			event = self.__states[state].deduceEvent(self.__states[future])

			prompt = f'\n{event} '
			if self.spoilers:
				prompt += self.__spoilerTag(future)
			print(prompt)

			active_player = not active_player
			state = future

		print('\nPlayer B won!' if active_player else '\nPlayer A won!')


# ---------------------------> Main


if __name__ == "__main__":
	cpu = AlphaDurak(SPADES, '9H 10S JS KS', 'AS QS QC JD JH 10H')
	cpu.play()