#!/usr/bin/env python3
# horror_house.py
# A terminal-based horror escape game written in Python.
# Every comment below starts with "#" as requested.

import random
import sys
import textwrap
import time

# ------------------------
# README shown to player
# ------------------------
README = """
Horror House - Python Terminal Game (Prototype)
-----------------------------------------------
Goal:
  - You are trapped in your house. Find 3 key pieces to escape.
  - Optionally, a secret 4th key may appear after finding all 3 parts.

Main mechanics:
  - Move between rooms, search for items and key parts.
  - A creature prowls the house. If it catches you, you lose.
  - You cannot fight normally — you can attempt to stun the creature or hide.
  - Stuns require stun items found in the house and dice-rolls.
  - Hiding uses hiding spots in rooms and agility checks.
  - Finding each key piece reveals backstory and unlocks new rooms.
  - Character classes affect stats and gameplay.

Controls:
  - When prompted, enter the number or letter for your choice.
  - Commands available during play: move, search, inventory, use, status, quit.

Note for coders:
  - Code is heavily commented. Functions are small and designed to be extended.
"""

# ------------------------
# Helper utilities
# ------------------------

# # small function to print text with a typewriter-like delay for atmosphere
def atmospheric_print(text, delay=0.008, wrap=70):
    # # wrap text to terminal-friendly width, then print char-by-char
    for line in textwrap.wrap(text, wrap):
        for ch in line:
            print(ch, end="", flush=True)
            time.sleep(delay)
        print()
    # # tiny pause after message for pacing
    time.sleep(0.2)

# # dice roll helper: "roll Dn" returns 1..n
def roll_dice(n=20):
    # # ensure dice is valid
    if n < 1:
        return 1
    return random.randint(1, n)

# # safe input with options: keeps prompting until valid choice selected
def choose(prompt, options):
    # # present options and require valid input
    while True:
        try:
            atmospheric_print(prompt)
            choice = input("> ").strip()
            if choice == "":
                print("Please enter a choice.")
                continue
            # # allow direct option matches (numbers/letters)
            if choice in options:
                return choice
            # # allow numeric selection if options are numeric strings
            if choice.isdigit() and choice in options:
                return choice
            print("Invalid choice. Options:", ", ".join(options))
        except (KeyboardInterrupt, EOFError):
            print("\nQuitting game.")
            sys.exit(0)
        except Exception as e:
            print("Input error:", e)

# ------------------------
# Game data structures
# ------------------------

# # Item base class
class Item:
    # # name: identifier, desc: description shown to player
    def __init__(self, name, desc):
        self.name = name
        self.desc = desc

    # # readable representation
    def __str__(self):
        return f"{self.name}: {self.desc}"

# # StunItem extends Item; has a strength that affects stun chance and uses
class StunItem(Item):
    def __init__(self, name, desc, strength=10, durability=1):
        super().__init__(name, desc)
        # # strength controls stun roll bonus
        self.strength = strength
        # # durability controls how many times it can be used
        self.durability = durability

    # # use reduces durability and returns True if usable
    def use(self):
        if self.durability <= 0:
            return False
        self.durability -= 1
        return True

# # KeyPart item; stores part index and backstory text to reveal when found
class KeyPart(Item):
    def __init__(self, part_id, desc, backstory):
        super().__init__(f"KeyPart{part_id}", desc)
        self.part_id = part_id
        self.backstory = backstory

# # Room class holds items, hiding spots, description, and adjacency info
class Room:
    def __init__(self, name, short_desc, long_desc, hiding_spots=1):
        self.name = name
        self.short_desc = short_desc
        self.long_desc = long_desc
        # # list of Item objects
        self.items = []
        # # number of hiding spots in room
        self.hiding_spots = hiding_spots
        # # adjacency mapping: direction name -> Room object (populated later)
        self.adjacent = {}
        # # whether the room is locked until a certain key part is found
        self.required_unlock_part = None
        # # story revealed when entering after unlocking
        self.reveal_text = None

    # # link this room with another (bidirectional)
    def link(self, other_room, name_from_self_to_other):
        self.adjacent[name_from_self_to_other] = other_room

    # # add item to room
    def add_item(self, item):
        self.items.append(item)

    # # remove an item instance from room
    def remove_item(self, item):
        if item in self.items:
            self.items.remove(item)

    # # check if the room is currently accessible (True if unlocked or no requirement)
    def is_accessible(self, found_parts):
        if self.required_unlock_part is None:
            return True
        return self.required_unlock_part in found_parts

# ------------------------
# Player and Creature
# ------------------------

# # Player class with stats, inventory, and actions
class Player:
    def __init__(self, name, character_class):
        self.name = name
        self.character_class = character_class
        # # base stats assigned by class: Strength, Agility, Magic
        self.strength = 0
        self.agility = 0
        self.magic = 0
        self.max_hp = 10
        self.hp = 10
        self.inventory = []  # # list of Item objects
        self.key_parts = []  # # list of KeyPart objects collected
        # # current room will be set by game bootstrapping
        self.current_room = None
        # # whether player is currently hiding (affects detection)
        self.is_hiding = False
        # # assign class stats
        self.assign_class_stats(character_class)

    # # apply class-based stats
    def assign_class_stats(self, character_class):
        # # default distribution (tweakable)
        if character_class.lower() == "warrior":
            self.strength = 7
            self.agility = 3
            self.magic = 2
            self.max_hp = 14
        elif character_class.lower() == "mage":
            self.strength = 2
            self.agility = 4
            self.magic = 8
            self.max_hp = 10
        elif character_class.lower() == "rogue":
            self.strength = 4
            self.agility = 8
            self.magic = 2
            self.max_hp = 11
        else:
            # # fallback balanced class
            self.strength = 5
            self.agility = 5
            self.magic = 5
            self.max_hp = 12
        # # set current HP to max at start
        self.hp = self.max_hp

    # # add item to inventory
    def pickup(self, item):
        self.inventory.append(item)

    # # find stun items in inventory
    def stun_items(self):
        return [it for it in self.inventory if isinstance(it, StunItem)]

    # # find key parts in inventory (stored separately in key_parts)
    def has_all_main_keys(self):
        # # main keys are parts 1-3
        ids = {kp.part_id for kp in self.key_parts}
        return {1, 2, 3}.issubset(ids)

# # Creature (enemy) with AI behavior
class Creature:
    def __init__(self, difficulty=1, name="The Crawling Thing"):
        self.name = name
        # # difficulty scales creature stats and behavior
        self.difficulty = difficulty
        # # base detection chance, attack strength, and health
        self.base_detection = 8 + difficulty * 2  # # lower means easier detection success
        self.attack_power = 1 + difficulty  # # damage per successful attack
        self.hp = 10 + difficulty * 5  # # creature health (for stun duration logic)
        # # cooldown before next special move
        self.cooldown = 0

    # # attempt to detect player in same room; returns True if creature notices player
    def detect_player(self, player, room):
        # # detection roll: creature rolls d20 + modifier vs player's hide roll
        creature_roll = roll_dice(20) + self.difficulty * 2
        # # player's hide ability: agility plus bonuses for hiding spots and being in hiding
        player_hide_score = player.agility + (room.hiding_spots * 1)
        if player.is_hiding:
            player_hide_score += 4  # # hiding gives a bonus
        # # random factor to keep things unpredictable
        player_hide_score += roll_dice(6)
        # # if creature roll > player hide score, it detects
        detected = creature_roll > player_hide_score
        return detected, creature_roll, player_hide_score

    # # creature attack: reduces player HP
    def attack(self, player):
        # # damage is attack_power plus a small random factor
        damage = self.attack_power + random.randint(0, self.difficulty)
        player.hp = max(0, player.hp - damage)
        return damage

    # # special move: lunging pounce that increases detection chance next turn
    def special_move(self, player):
        # # special move effects: next detection roll boosted, immediate small damage
        if self.cooldown > 0:
            return None
        self.cooldown = 3 + self.difficulty  # # cooldown before next special
        damage = max(1, self.attack_power // 2)
        player.hp = max(0, player.hp - damage)
        # # return description and damage
        return ("pounce", damage)

    # # called each turn to tick down cooldowns
    def tick(self):
        if self.cooldown > 0:
            self.cooldown -= 1

# ------------------------
# World creation
# ------------------------

# # create a set of rooms and interlink them; some rooms locked until certain key parts found
def create_world():
    # # instantiate rooms with descriptions and hiding spot counts
    foyer = Room(
        "Foyer",
        "A dim foyer with a coat rack and a cracked mirror.",
        "The foyer smells faintly of dust and old smoke. The front door is barred from the outside.",
        hiding_spots=1,
    )
    living = Room(
        "Living Room",
        "A cluttered living room with overturned furniture.",
        "Old newspapers pile in corners. There's an eerie silence; the TV is cold.",
        hiding_spots=2,
    )
    kitchen = Room(
        "Kitchen",
        "A tiled kitchen with broken plates.",
        "Cabinets hang open; a faint trail of dried liquid leads under the sink.",
        hiding_spots=1,
    )
    basement = Room(
        "Basement",
        "A cold basement with a humming furnace.",
        "The basement is dark and low-ceilinged. Ducts scrape above you.",
        hiding_spots=2,
    )
    bedroom = Room(
        "Bedroom",
        "A master bedroom with a canopy bed.",
        "The bed is unmade as though someone left in a hurry. The closet door creaks.",
        hiding_spots=1,
    )
    attic = Room(
        "Attic",
        "A dusty attic accessible by ladder.",
        "The attic is full of trunks and old toys. Something seems to have been moved recently.",
        hiding_spots=3,
    )
    study = Room(
        "Study",
        "A small study lined with books.",
        "A journal lies open on the desk. The window looks out over the street.",
        hiding_spots=1,
    )

    # # connect rooms (bidirectional links)
    foyer.link(living, "north")
    living.link(foyer, "south")
    living.link(kitchen, "east")
    kitchen.link(living, "west")
    living.link(study, "west")
    study.link(living, "east")
    kitchen.link(basement, "down")
    basement.link(kitchen, "up")
    living.link(bedroom, "north")
    bedroom.link(living, "south")
    bedroom.link(attic, "up")
    attic.link(bedroom, "down")

    # # assign unlock requirements: some rooms only become accessible after finding a certain key part
    basement.required_unlock_part = 1  # # basement opens after finding key part 1
    basement.reveal_text = "You discover a hatch in the kitchen floor that leads down. The keypart you found whispers the way."

    attic.required_unlock_part = 2  # # attic opens after finding key part 2
    attic.reveal_text = "With the second key part a loose board creaks; a ladder descends to the attic."

    study.required_unlock_part = 3  # # study opens after finding key part 3
    study.reveal_text = "The third keypiece hums and a shelf slides aside, revealing the study."

    # # return entry point and mapping of rooms for random placement convenience
    rooms = [foyer, living, kitchen, basement, bedroom, attic, study]
    return foyer, rooms

# ------------------------
# Game logic
# ------------------------

# # assemble the key part backstories (revealed sequentially)
BACKSTORIES = {
    1: "Key Part 1: A smeared drawing of the creature. It was once someone you knew.",
    2: "Key Part 2: A note: 'It keeps the house sealed. It remembers.'",
    3: "Key Part 3: A photograph of the family at the doorway — the edges charred.",
    4: "Secret Key: Etched into the metal: 'Choice — leave, or stay and learn.'"
}

# # Main Game class
class Game:
    def __init__(self):
        # # create world and starting room
        self.start_room, self.rooms = create_world()
        # # create the creature with a difficulty level that can vary by character choice
        self.creature = Creature(difficulty=1)
        # # placeholder for player, set on new_game()
        self.player = None
        # # set of part ids found (for room unlocking and checks)
        self.found_parts = set()
        # # secret 4th key appears only after all main 3 are found with some random chance
        self.secret_key_spawned = False
        # # seed randomness for reproduciblity if desired (not seeded by default)
        random.seed()

    # # welcome and character creation
    def new_game(self):
        # # print README and intro
        print(README)
        atmospheric_print("The house is quiet. The front door will not open.")
        # # choose character
        classes = {"1": "Warrior", "2": "Mage", "3": "Rogue"}
        atmospheric_print("Choose your character class:")
        for k, v in classes.items():
            atmospheric_print(f"  {k}. {v}")
        choice = choose("Enter 1, 2 or 3:", list(classes.keys()))
        chosen_class = classes[choice]
        try:
            name = input("Enter your character name: ").strip()
            if not name:
                name = "Player"
        except Exception:
            name = "Player"
        # # instantiate player and set start room
        self.player = Player(name, chosen_class)
        self.player.current_room = self.start_room
        # # difficulty tweak by class: tougher creature vs higher-level classes
        if chosen_class == "Warrior":
            self.creature.difficulty = 1
        elif chosen_class == "Mage":
            self.creature.difficulty = 1
        elif chosen_class == "Rogue":
            self.creature.difficulty = 2  # # rogues get harder creature for challenge
        # # place items and key parts randomly across accessible rooms
        self.scatter_items_and_keys()
        atmospheric_print(f"Welcome, {self.player.name} the {self.player.character_class}.")
        atmospheric_print("Find three key parts to assemble a key and escape. Beware the creature.")

    # # scatter items and key parts randomly across rooms
    def scatter_items_and_keys(self):
        # # potential stun items pool (name, desc, strength, durability)
        stun_item_defs = [
            ("Fire Extinguisher", "A heavy canister. A good blunt stun.", 8, 1),
            ("Metal Lamp", "A bedside lamp; swing it to daze.", 5, 2),
            ("Stun Spray", "A small chemical canister; temporarily stuns.", 10, 1),
            ("Rock", "A crude rock found in the yard.", 3, 3),
        ]
        # # create StunItem objects and place randomly
        rooms_copy = list(self.rooms)
        random.shuffle(rooms_copy)
        for i, (n, d, s, dur) in enumerate(stun_item_defs):
            room = rooms_copy[i % len(rooms_copy)]
            room.add_item(StunItem(n, d, s, dur))
        # # place some generic items (potions etc.)
        potion = Item("Health Potion", "Restores some health when used.")
        random.choice(self.rooms).add_item(potion)
        # # create key parts 1..3 and scatter across rooms that are initially accessible
        main_rooms = [r for r in self.rooms if r.is_accessible(self.found_parts)]
        random.shuffle(main_rooms)
        # # ensure 3 distinct rooms get parts
        candidate_rooms = main_rooms[:3] if len(main_rooms) >= 3 else main_rooms
        # # fallback: if not enough accessible rooms, use all rooms
        if len(candidate_rooms) < 3:
            candidate_rooms = random.sample(self.rooms, 3)
        for idx, room in enumerate(candidate_rooms, start=1):
            kp = KeyPart(idx, f"A tarnished key fragment ({idx})", BACKSTORIES[idx])
            room.add_item(kp)
        # # ensure there is at least one hiding spot item etc. (already part of room)
        # # secret key not placed yet

    # # main game loop
    def run(self):
        # # loop until win or lose
        while True:
            # # check lose condition: caught by creature (hp 0)
            if self.player.hp <= 0:
                atmospheric_print("You collapse as the creature's jaws close. You have been caught.")
                self.end_game(lost=True)
                break
            # # check win condition: player has assembled all main 3 key parts and used them to escape
            if self.player.has_all_main_keys():
                # # require explicit 'escape' action at exit (foyer) to win
                if self.player.current_room == self.start_room:
                    atmospheric_print("You stand at the front door with the key assembled across your palm.")
                    atmospheric_print("Do you use it to unlock the door?")
                    choice = choose("1. Use key to escape\n2. Wait and explore more", ["1", "2"])
                    if choice == "1":
                        atmospheric_print("The lock clicks. The door opens into the cold night. You step out.")
                        self.end_game(lost=False)
                        break
                    else:
                        atmospheric_print("You decide to stay a little longer, curiosity winning over fear.")
                # # otherwise continue exploring until you return to foyer
            # # present current room and options
            self.describe_current_room()
            # # creature movement: simple AI — sometimes moves between rooms randomly
            self.creature_tick()
            # # present player action choices
            self.player_turn()
            # # creature turn if in same room
            if self.player.current_room == self.get_creature_location():
                # # resolve encounter
                self.handle_encounter()
            # # tick creature state
            self.creature.tick()
            # # occasionally spawn secret key if all main parts found and not yet spawned
            if self.player.has_all_main_keys() and not self.secret_key_spawned:
                if random.random() < 0.6:  # # 60% chance to spawn
                    self.spawn_secret_key()

    # # describe player's current room, its items, available exits, and story reveal when unlocking
    def describe_current_room(self):
        room = self.player.current_room
        # # if room wasn't accessible previously and now is being entered after unlock, reveal story
        if room.required_unlock_part and room.required_unlock_part in self.found_parts and room.reveal_text:
            atmospheric_print(room.reveal_text)
            # # avoid repeating reveal
            room.reveal_text = None
        atmospheric_print(f"You are in the {room.name}. {room.short_desc}")
        atmospheric_print(room.long_desc)
        # # list items
        if room.items:
            atmospheric_print("You notice the following items:")
            for idx, it in enumerate(room.items, start=1):
                atmospheric_print(f"  {idx}. {it.name} - {it.desc}")
        else:
            atmospheric_print("No obvious items are visible.")
        # # list exits
        exits = list(room.adjacent.keys())
        if exits:
            atmospheric_print("Exits: " + ", ".join(exits))
        else:
            atmospheric_print("No visible exits.")

    # # placeholder creature location: creature patrols randomly; for simplicity we assign a room index
    # # we track creature location by index into self.rooms list; start creature at random room different from player
    def get_creature_location(self):
        if not hasattr(self, "_creature_room_index"):
            # # choose random room not equal to player's current
            possible = [i for i, r in enumerate(self.rooms) if r != self.player.current_room]
            self._creature_room_index = random.choice(possible)
        return self.rooms[self._creature_room_index]

    # # move creature randomly with a chance to move towards player if recently detected
    def creature_tick(self):
        # # small chance to move randomly
        if random.random() < 0.5:
            # # move to a random adjacent room to current creature room (if any)
            cur = self.get_creature_location()
            if cur.adjacent:
                next_room = random.choice(list(cur.adjacent.values()))
                # # set new creature index
                self._creature_room_index = self.rooms.index(next_room)
        # # if creature is currently in player's room and detects movement, handle detection in encounter
        # # nothing further in tick

    # # player actions (move, search, hide, use item, inventory, status, quit)
    def player_turn(self):
        options = {
            "1": "Move",
            "2": "Search",
            "3": "Hide/Unhide",
            "4": "Inventory",
            "5": "Use Item",
            "6": "Status",
            "7": "Quit"
        }
        atmospheric_print("Choose an action:")
        for k, v in options.items():
            atmospheric_print(f"  {k}. {v}")
        choice = choose("Enter action number:", list(options.keys()))
        try:
            if choice == "1":
                self.action_move()
            elif choice == "2":
                self.action_search()
            elif choice == "3":
                self.action_hide()
            elif choice == "4":
                self.show_inventory()
            elif choice == "5":
                self.action_use_item()
            elif choice == "6":
                self.show_status()
            elif choice == "7":
                atmospheric_print("Are you sure you want to quit? Progress will be lost.")
                if choose("Quit? (y/n)", ["y", "n"]) == "y":
                    self.end_game(lost=True)
                    sys.exit(0)
            else:
                print("Unknown action.")
        except Exception as e:
            print("Action error:", e)

    # # movement action: list accessible exits and perform move
    def action_move(self):
        room = self.player.current_room
        # # build list of accessible adjacent rooms considering unlock requirements
        accessible = {}
        idx = 1
        for name, r in room.adjacent.items():
            if r.is_accessible(self.found_parts):
                accessible[str(idx)] = (name, r)
                idx += 1
        if not accessible:
            atmospheric_print("No accessible exits from here.")
            return
        atmospheric_print("Where do you want to go?")
        for k, (n, r) in accessible.items():
            atmospheric_print(f"  {k}. {n} - {r.short_desc}")
        choice = choose("Enter destination number:", list(accessible.keys()))
        chosen = accessible[choice][1]
        self.player.current_room = chosen
        self.player.is_hiding = False  # # moving cancels hiding
        atmospheric_print(f"You move to the {chosen.name}.")

    # # search action: attempt to find items in room; chance to trigger creature detection if in same room
    def action_search(self):
        room = self.player.current_room
        # # if no items, small chance to find a hidden object
        if not room.items:
            # # chance to find something small (rare)
            if random.random() < 0.2:
                found = Item("Rusty Key", "Probably not the escape key, but something.")
                room.add_item(found)
                atmospheric_print("While searching you find something: Rusty Key.")
            else:
                atmospheric_print("You search but find nothing of note.")
            return
        # # present items and allow pickup
        options = {str(i + 1): it for i, it in enumerate(room.items)}
        atmospheric_print("Which item do you want to pick up?")
        for k, it in options.items():
            atmospheric_print(f"  {k}. {it.name} - {it.desc}")
        atmospheric_print("  0. Cancel")
        valid = list(options.keys()) + ["0"]
        choice = choose("Enter number:", valid)
        if choice == "0":
            atmospheric_print("You leave the items untouched.")
            return
        item = options[choice]
        # # if item is a KeyPart, picking it up reveals backstory and unlocks rooms
        if isinstance(item, KeyPart):
            self.player.pickup(item)
            self.player.key_parts.append(item)
            # # mark part as found for unlock logic
            self.found_parts.add(item.part_id)
            atmospheric_print(f"You found a key piece! {item.desc}")
            atmospheric_print(item.backstory)
            # # after picking part, remove it from room
            room.remove_item(item)
            # # unlock rooms depending on part found; scanning rooms to see which require that part
            for r in self.rooms:
                if r.required_unlock_part == item.part_id:
                    # # now the room is accessible; reveal text will be shown on entry
                    r.reveal_text = getattr(r, "reveal_text", None)
                    atmospheric_print(f"A distant click echoes; new paths might be open.")
            return
        else:
            # # pick up generic item
            self.player.pickup(item)
            atmospheric_print(f"You pick up {item.name}.")
            room.remove_item(item)
            return

    # # hide/unhide: toggle hiding. Success modified by agility and room hiding spots when creature attempts detection.
    def action_hide(self):
        room = self.player.current_room
        if self.player.is_hiding:
            self.player.is_hiding = False
            atmospheric_print("You step out of your hiding place.")
            return
        if room.hiding_spots <= 0:
            atmospheric_print("There is nowhere obvious to hide here.")
            return
        # # attempt to hide: agility + small roll compared to difficulty threshold
        hide_roll = self.player.agility + roll_dice(6)
        # # rogues get small bonus
        if self.player.character_class.lower() == "rogue":
            hide_roll += 2
        if hide_roll >= 6:
            self.player.is_hiding = True
            atmospheric_print("You slip into a hiding place and hold your breath.")
        else:
            atmospheric_print("You try to hide but fail to conceal yourself properly.")
            self.player.is_hiding = False

    # # show inventory and allow using consumable items from inventory
    def show_inventory(self):
        inv = self.player.inventory
        if not inv:
            atmospheric_print("Your inventory is empty.")
            return
        atmospheric_print("Inventory:")
        for i, it in enumerate(inv, start=1):
            if isinstance(it, StunItem):
                atmospheric_print(f"  {i}. {it.name} (Stun strength {it.strength}, uses left {it.durability})")
            else:
                atmospheric_print(f"  {i}. {it.name} - {it.desc}")
        # # show key parts
        if self.player.key_parts:
            atmospheric_print("Key Parts collected:")
            for kp in self.player.key_parts:
                atmospheric_print(f"  - Part {kp.part_id}")

    # # using item from inventory: on-use effects (health potion, stun items, secret behaviors)
    def action_use_item(self):
        inv = self.player.inventory
        if not inv:
            atmospheric_print("No items to use.")
            return
        atmospheric_print("Which item do you want to use?")
        for i, it in enumerate(inv, start=1):
            atmospheric_print(f"  {i}. {it.name} - {it.desc}")
        atmospheric_print("  0. Cancel")
        valid = [str(i) for i in range(len(inv) + 1)]
        choice = choose("Enter number:", valid)
        if choice == "0":
            atmospheric_print("You don't use anything.")
            return
        idx = int(choice) - 1
        if idx < 0 or idx >= len(inv):
            atmospheric_print("That selection is invalid.")
            return
        item = inv[idx]
        # # Stun items can't be "used" here directly except when in creature encounter; but we allow prepping: using a stun item readies it (no cost)
        if isinstance(item, StunItem):
            # # allow the player to throw/swing stun immediately if creature is present
            if self.player.current_room == self.get_creature_location():
                # # attempt stun immediately
                success = self.attempt_stun(item)
                if item.durability <= 0:
                    # # remove if durability exhausted
                    self.player.inventory.remove(item)
                # # if stunned, creature loses a turn (we simulate by moving it away)
                return
            else:
                atmospheric_print(f"You hold {item.name} at the ready.")
                return
        # # Health potion usage
        if item.name.lower().startswith("health"):
            heal_amount = 3 + roll_dice(4)
            self.player.hp = min(self.player.max_hp, self.player.hp + heal_amount)
            atmospheric_print(f"You use the potion and restore {heal_amount} HP.")
            # # remove used potion
            self.player.inventory.remove(item)
            return
        # # generic use has no immediate effect
        atmospheric_print("You examine it carefully but nothing happens.")

    # # show player status
    def show_status(self):
        p = self.player
        atmospheric_print(f"{p.name} the {p.character_class} — HP: {p.hp}/{p.max_hp}")
        atmospheric_print(f"STR: {p.strength}  AGI: {p.agility}  MAG: {p.magic}")
        atmospheric_print(f"Key parts: {', '.join(str(k.part_id) for k in p.key_parts) if p.key_parts else 'None'}")

    # # handle encounter when creature shares room with player
    def handle_encounter(self):
        room = self.player.current_room
        creature_room = self.get_creature_location()
        # # verify in same room
        if room != creature_room:
            return
        atmospheric_print("You sense movement. The creature is here.")
        # # detection check
        detected, c_roll, p_hide = self.creature.detect_player(self.player, room)
        # # reveal rolls for transparency (could be hidden for more horror)
        atmospheric_print(f"(Rolls) Creature: {c_roll} vs Player hide score: {p_hide}")
        if detected:
            atmospheric_print("The creature spots you!")
            # # combat loop until either player escapes/hidden or stun or creature leaves
            while True:
                # # present actions while creature present: stun (if item), hide (attempt), move (risky), use (potion), run (move), surrender
                options = {"1": "Attempt to Stun", "2": "Attempt to Hide", "3": "Move (risky)", "4": "Use Item", "5": "Surrender (quit)"}
                atmospheric_print("Options:")
                for k, v in options.items():
                    atmospheric_print(f"  {k}. {v}")
                choice = choose("Choose:", list(options.keys()))
                if choice == "1":
                    # # attempt stun if any stun items in inventory
                    stun_items = self.player.stun_items()
                    if not stun_items:
                        atmospheric_print("You have nothing that can stun the creature.")
                        continue
                    # # let player pick which stun item
                    atmospheric_print("Which stun item to use?")
                    for i, it in enumerate(stun_items, start=1):
                        atmospheric_print(f"  {i}. {it.name} (strength {it.strength}, uses {it.durability})")
                    pick_opts = [str(i) for i in range(1, len(stun_items) + 1)]
                    pick = choose("Choose item number:", pick_opts)
                    stun_item = stun_items[int(pick) - 1]
                    # # attempt stun
                    success = self.attempt_stun(stun_item)
                    # # if stun successful, move creature away a bit (simulate stun removal)
                    if success:
                        atmospheric_print("You have stunned the creature! You have a moment to move away.")
                        # # move creature to a random adjacent room (if possible)
                        if creature_room.adjacent:
                            target = random.choice(list(creature_room.adjacent.values()))
                            self._creature_room_index = self.rooms.index(target)
                        else:
                            # # if no adjacent, creature remains but stunned (skip its next action)
                            pass
                        break
                    else:
                        # # failed stun -> creature gets an attack
                        dmg = self.creature.attack(self.player)
                        atmospheric_print(f"Stun failed. The creature attacks and deals {dmg} damage.")
                        if self.player.hp <= 0:
                            return
                        continue
                elif choice == "2":
                    # # attempt to hide; lower chance because creature already saw you (harder)
                    hide_roll = self.player.agility + roll_dice(6)
                    if self.player.character_class.lower() == "rogue":
                        hide_roll += 2
                    # # room hiding spots improve odds
                    hide_roll += room.hiding_spots
                    atmospheric_print(f"You attempt to hide... (roll {hide_roll})")
                    if hide_roll >= (8 + self.creature.difficulty * 2):
                        self.player.is_hiding = True
                        atmospheric_print("You dive behind cover and hold perfectly still. The creature loses sight of you.")
                        # # creature searches but may leave
                        if random.random() < 0.5:
                            # # creature moves away
                            if creature_room.adjacent:
                                target = random.choice(list(creature_room.adjacent.values()))
                                self._creature_room_index = self.rooms.index(target)
                        break
                    else:
                        atmospheric_print("Your hiding fails; you are still exposed.")
                        dmg = self.creature.attack(self.player)
                        atmospheric_print(f"The creature slashes you for {dmg} damage.")
                        if self.player.hp <= 0:
                            return
                        continue
                elif choice == "3":
                    # # moving while creature present has chance to escape but also to be caught
                    escape_roll = self.player.agility + roll_dice(6)
                    atmospheric_print(f"You try to move away quickly... (roll {escape_roll})")
                    if escape_roll > (10 + self.creature.difficulty):
                        # # pick a random adjacent room to move into (if any)
                        if room.adjacent:
                            dest = random.choice(list(room.adjacent.values()))
                            self.player.current_room = dest
                            self.player.is_hiding = False
                            atmospheric_print(f"You bolt into the {dest.name}.")
                            # # creature may follow with some chance
                            if random.random() < 0.6:
                                self._creature_room_index = self.rooms.index(dest)
                            break
                        else:
                            atmospheric_print("There is nowhere to run!")
                            dmg = self.creature.attack(self.player)
                            atmospheric_print(f"The creature attacks and deals {dmg} damage.")
                            if self.player.hp <= 0:
                                return
                            continue
                    else:
                        dmg = self.creature.attack(self.player)
                        atmospheric_print(f"You fail to escape. The creature strikes you for {dmg} damage.")
                        if self.player.hp <= 0:
                            return
                        continue
                elif choice == "4":
                    self.action_use_item()
                    # # using items may or may not provoke attack; resume loop
                    continue
                elif choice == "5":
                    atmospheric_print("You accept your fate. The game ends.")
                    self.end_game(lost=True)
                    sys.exit(0)
                else:
                    atmospheric_print("Invalid choice.")
        else:
            atmospheric_print("You hold your breath and the creature does not notice you... for now.")
            # # small chance creature might still sniff around and leave
            if random.random() < 0.2:
                if creature_room.adjacent:
                    target = random.choice(list(creature_room.adjacent.values()))
                    self._creature_room_index = self.rooms.index(target)

    # # attempt stun using item; returns True if stun succeeded
    def attempt_stun(self, stun_item):
        # # consume a use
        if not stun_item.use():
            atmospheric_print("The item is depleted.")
            try:
                self.player.inventory.remove(stun_item)
            except ValueError:
                pass
            return False
        # # stun success: player roll + item strength + relevant stat vs creature defense
        player_roll = roll_dice(20) + stun_item.strength + (self.player.strength // 2)
        creature_defense = 12 + self.creature.difficulty * 3 + roll_dice(6)
        atmospheric_print(f"(Stun rolls) You: {player_roll} vs Creature defense: {creature_defense}")
        if player_roll >= creature_defense:
            # # creature stunned: reduce its hp to simulate incapacitance; or move away
            # # represent stun by moving creature away or reducing its capacity to act
            atmospheric_print("It staggers and collapses briefly — stunned.")
            # # chance of long stun if roll high or magic used
            if player_roll >= creature_defense + 8 or self.player.magic > 6:
                atmospheric_print("The creature is stunned for longer; you hear it retreat.")
                if self.get_creature_location().adjacent:
                    target = random.choice(list(self.get_creature_location().adjacent.values()))
                    self._creature_room_index = self.rooms.index(target)
            # # if item used up, remove
            try:
                if stun_item.durability <= 0:
                    self.player.inventory.remove(stun_item)
            except ValueError:
                pass
            return True
        else:
            atmospheric_print("The stun attempt fails; the creature shakes it off.")
            try:
                if stun_item.durability <= 0:
                    self.player.inventory.remove(stun_item)
            except ValueError:
                pass
            return False

    # # spawn secret key in a random room (not the start) after main keys found
    def spawn_secret_key(self):
        candidate_rooms = [r for r in self.rooms if r != self.start_room]
        room = random.choice(candidate_rooms)
        secret = KeyPart(4, "A cold, ornate key that hums faintly.", BACKSTORIES[4])
        room.add_item(secret)
        self.secret_key_spawned = True
        atmospheric_print("You feel a strange pull. Somewhere in the house, something else stirs...")

    # # end game print message and exit
    def end_game(self, lost=False):
        if lost:
            atmospheric_print("GAME OVER. The house took you.")
        else:
            atmospheric_print("CONGRATULATIONS. You escaped the house.")
            # # if secret key was found, show optional alternative ending
            if any(k.part_id == 4 for k in self.player.key_parts):
                atmospheric_print("You also possess the secret key. As you step out, a choice whispers: return and learn the truth, or leave and forget.")
        atmospheric_print("Thank you for playing.")
        sys.exit(0)

# ------------------------
# Entry point for execution
# ------------------------

def main():
    # # create and run the game with exception handling
    try:
        game = Game()
        game.new_game()
        game.run()
    except Exception as e:
        # # catch unexpected errors and present a friendly message (error handling)
        print("An unexpected error occurred:", e)
        print("The game encountered an issue and must exit.")
        sys.exit(1)

if __name__ == "__main__":
    main()

# ------------------------
# README and developer notes (end of file)
# ------------------------
# README_CONTENT:
# - Save this file as horror_house.py and run `python horror_house.py`.
# - The game is a prototype. To extend:
#   * Add more rooms and richer story text.
#   * Improve creature AI (patrol paths, memory, sense thresholds).
#   * Persist game state, add save/load.
#   * Hook into Pygame or Godot for graphical UI; keep the logic classes Player, Creature, Room.
# - Each function is annotated with comments starting with '#'.
# - Error handling: top-level try/except in main; input validated in choose() helper.
#
# Design notes:
# - World unlocking: rooms have required_unlock_part attribute; when part found they become accessible.
# - Combat: turn-based decision loop inside handle_encounter() with dice rolls.
# - Randomness: roll_dice() centralizes randomness and allows modification.
# - Inventory: stun items are StunItem; durability consumed on use.
# - Character classes change stats which affect hide/stun outcomes.
#
# Legal / Safety:
# - This game contains horror themes but no explicit gore.
# - Use responsibly; the text output is safe for a general audience.
#
# Enjoy and modify as you like!
