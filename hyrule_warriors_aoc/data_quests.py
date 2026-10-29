"""
Side quests, captured from published guides (GameFAQs quest guide). The base game has 376 quests; this
table captures the ones the sources listed (see EXPECTED_COUNT / the module-level note below).
Quests are material turn-ins; materials are assumed obtainable (logic only models *access*).

Format of QUEST_TABLE:
  "## <gate>" starts a block; every quest below inherits that gate. Gates:
        <mission name>   the quest unlocks after clearing that story mission
        ANY2             after clearing any Chapter 2 mission
        FOUR2            after clearing four of the five Chapter 2 missions
        HOPE             after finishing the story (meta quests such as "The Hope of ..." which need
                         other quests; the exact membership is unknown so logic is conservative)
  "<quest name> | q:<quest>; c:<challenge>; gate=<mission>"   optional extras on a quest line:
        q:  another quest must be completed first
        c:  a challenge must be completed first
        gate=  overrides the block's gate for this quest

NAMES come from the game's own text (the player's dump): 381 base quests + 77 Expansion Pass "EX" quests.
Entries from the original guide keep their gates/prerequisites; quests added from the dump are gated
conservatively (HOPE = after the story) until their real unlock conditions are read from the game data.
"""

from __future__ import annotations

from typing import NamedTuple

CHAPTER_TWO_MISSIONS = (
    "Mipha, the Zora Princess",
    "Daruk, the Goron Hero",
    "Revali, the Rito Warrior",
    "Urbosa, the Gerudo Chief",
    "The Yiga Clan Attacks!",
)


class Quest(NamedTuple):
    name: str
    gate: str  # mission name, "ANY2", "FOUR2" or "HOPE"
    quest_prereqs: tuple[str, ...] = ()
    challenge_prereqs: tuple[str, ...] = ()

    @property
    def is_ex(self) -> bool:
        return self.name.startswith("EX ")


QUEST_TABLE = """
## The Battle of Hyrule Field
Hyrule Swordfighting Academy
Hot Meals in a Pot
Keeping the Village Peace | q:Hyrule Swordfighting Academy
A Feast of Greens | q:Hot Meals in a Pot

## Road to the Ancient Lab
The Lights of Home
Traps for Kakariko Village | q:The Lights of Home
The Frontiers of Knowledge
Pumpkin Burglars
On the Hook
Anything but Bugs
Swanked-Up Stable | q:On the Hook
Brawny Blacksmiths
A Well-Tended Goddess | q:Keeping the Village Peace

## ANY2
Kakariko's Best Babysitter
Entrance Test
Relief for Soldier Stress
A Birthday Treat
Superb Fish Dish
Needed: Researchers!

## FOUR2
Shop-Quick Store
A Spear-ited Combatant
Study the Blade
The Hateno Defense Squad

## Mipha, the Zora Princess
The Zora Who Wouldn't Swim
A Fruitful Offering
A Princess in Distress | q:Relief for Soldier Stress
An End to Fighting
Climbing the Waterfall | c:Mipha's Training

## Daruk, the Goron Hero
Making a Monster
A Buffet of Delicacies
A Battle against the Heat
The Creative Fires
Playing with Fire | c:Daruk's Training
Gotta Have a Sign
Hoping for Heat Relief
Dyeing to Make Contact

## Revali, the Rito Warrior
Cooking for the Common Cold
Learning to Become the Wind | c:Revali's Training
A Flower-Adorned Goddess
Upgrading the Flight Range
The Lodge at Hebra Trailhead
Brilliance for the Boutique
Best-Ever Batter

## Urbosa, the Gerudo Chief
Urbosa's Desert Training
Conducting an Experiment
Shocking Design Choices | c:Urbosa's Training
Wanted: Shop Assistant
Who's Shocked by Lightning?

## The Yiga Clan Attacks!
Mount Taran's Solitary Masters
An Irresistible Aroma
A Fly-by-Night Operation
Painter's Pilgrimage
To Bring the Village Together | c:Impa's Training
Bounding Across the Waves
Help Them on Their Way

## Freeing Korok Forest
The Blade that Pierces the Eye
Heartfelt Thanks | q:The Blade that Pierces the Eye
Proof of Sword Mastery | q:Heartfelt Thanks
Village Training Secrets
Preparing for Field Work
To the Zora Voe and Vai
Playing Cucco
Beyond the Wall of Thunder
Colorful Kara Kara Bazaar
Pinwheel, No-Spinwheel
Frown-Reversal Magic
Otherworldly Objects
From Rusty to Trusty
More Rattle, More Dance!
The Korok Ballet | q:More Rattle, More Dance!

## The Road Home, Besieged
Diving Safety
Feeding the Laborers
These Muscles of Mine(rs)
Gut-Check Challenge
The Rito Flying Tournament
Across Tanagar Canyon
Conducive to Conducting
The Spa's New Service
Chilly Path to a Hot Bath
The Finest Tailor in the Land
A Read on the Enemy
Good Cheer
A Most Peculiar Korok | q:Good Cheer

## Akkala Tower
The Treasure Hunter's Technique
Training Ground Pest Problem
A Moss-Covered Goddess
Frog Side Effects
Helping Out at Hateno Pasture
Soothing Tensions
In Case of Emergency...
To Stand atop the Lava
Stealth Mission
Out of the Woods
The Mushroom Shop
It's Shakala Time
Offering Help on the Road
Explosive Endeavors
Shocking Fear
A Stasis on Research
Keep a Cool Head
What Bad Weather?
Lighting the Way
Tactics for Small Foes
A Sparkling Solution
A Rumor about Skull Lake
Stumped by Shrooms
Feed the Research
Diving as Battle Training | c:Mipha's Training
Curry Connoisseur | q:A Rumor about Skull Lake
Only the Best | c:Fairy Fountain: Battlefield
Luminous Earrings | c:Fairy Fountain: Battlefield
Glorious Ring | c:Fairy Fountain: Battlefield
Stunning Bracelet | c:Fairy Fountain: Battlefield
Superb Necklace | c:Fairy Fountain: Battlefield
No Stone Unturned | c:Fairy Fountain: Battlefield
Encouraging Tourism | c:Fairy Fountain: Battlefield
Dusty Desert Road | c:Fairy Fountain: Battlefield
Lushify the Spring | c:Fairy Fountain: Battlefield
Shimmering Horseshoe | c:Fairy Fountain: Battlefield; q:Superb Necklace

## HOPE
The Hope of All Hyrule
The Hope of Central Hyrule
The Hope of Hebra
The Hope of Akkala
The Hope of Eldin
The Hope of Lanayru
The Hope of Necluda
The Hope of Faron
The Hope of Gerudo

## Destroy the Yiga Clan!
The Research of Rods
Lauding a Champion
A Goron-Style Massage
A Leaf on the Breeze
Master Monster Roasts
A Balm for the Soul
The Trial of Monsters
The Trial of Stones
The Trial of the Mighty Foe
Trial of Dah Hesho | c:Trial of the Ancients
Trial of Soh Kofi | c:Trial of the Ancients
Trial of Ke'nai Shakah | c:Trial of the Ancients
Trial of Muwo Jeem | c:Trial of the Ancients
Trial of Tutsuwa Nima | c:Trial of the Ancients
Trial of Pumaag Nitae | c:Trial of the Ancients
Trial of Noya Neha | c:Trial of the Ancients
Trial of Shoqa Tatone | c:Trial of the Ancients
Trial of Sasa Kai | c:Trial of the Ancients
Trial of Goma Asaagh | c:Trial of the Ancients
Trial of Saas Ko'sah | c:Trial of the Ancients

## When Courage Fails
Just the Right Light
Research Funding
Regulating the Reservoir
Surveying the Volcano
Revitalize Those in the Skies
Patrolling the Desert
Inner Knowing
Inner Protection
Just like Mama Made
Soured Honeymoon

## Calamity Strikes
Training Ground Upgrade
Living Things of Hyrule
Think Yourself Clever?
Extreme Survival Cuisine

## Water and Fire
Sidon's Waterfall Workshop
The Zora Researcher
A Thirst for the Desert
Blessing of the Rains
Goron Rations
The Rock-Hard Grill
Defend the Goron Hot Springs
Fighting Fire With...
Bounty of the Sea
For the Future | c:Sidon's Training
What Do Guardians Taste Like? | c:Yunobo's Training
To Eat a Stone Pebblit? | c:Yunobo's Training

## Air and Lightning
The Blessing of Deya Lake
Parade for the Champions
The Great Cucco Escape
Finding Courage
The White Bird of Talonto Peak
Truffle Hunting in the Forest
Faster and Farther Than Anyone
Flight-Range Field Trip
Seal the Deal
"Voe and You" Is in Session
My Beloved Yellow
Dish for a Diva
Surviving the Gerudo Highlands
Caring for the Statues
The Missing Sand Seals | c:Riju's Training
Flight Training at Lake Totori | c:Teba's Training
A Wish for a Fishy Dish | q:Dish for a Diva

## Relentless as a Waterfall
The Strongest String
Refuel Motivation
A Frozen-Solid Goddess
Imported Goods
Armor for Whom?
Fine Goron Dining
Enduring Death Mountain
Scouting the Training Ground
At All Hours
A Surprise Reward
Rebuilding Lipstique
Shiny New Tools
A Monumental Undertaking
Cold Desert Nights
Lightning-Proof Luncheon
Really New Recipe
Unexpected Discovery
Birthday Waltz
Secret of the Rito Artisans | c:Daily Drills: Rito
Duel on Ploymus Mountain | q:Scouting the Training Ground
The Treasure Detector | c:Lost Treasures

## Each Step Like Thunder
The Knight's Gauntlet
The Kakariko Village Dojo
King Dorephan's Defenses
Bolstering Goron City
Joint Training with the Rito
Joint Training with the Gerudo
A Modest Celebration
Research Materials
An Offering to the Rito Goddess
Flight Across Hyrule
The Summer Breeze Festival
Gerudo Nail Artistry
A Goron Wrestling Tournament
Helping with Heights
Chasing Mipha
Not a Light Meal
The Rock Hurler
Rito Rations
The Sapphire Seal Pageant
Quality Time with Patricia
Spicy Asceticism
Chilly Asceticism
Hoppy Asceticism
Market Apeel
Veggie Vigor
Time for an Upgrade
Eager Learners in Hateno Village
It Takes Two
Wedding Worry
Floria Bridge Protection
Fine Bites from Lurelin Village
Bee Very Careful
The Sweetest Salsa
Upgrading the Detector
Eternal Blooms | q:Research Materials
A Sweet Desert Garden | q:Eternal Blooms
Bonananza | q:Market Apeel
Better Rust-Busting | q:From Rusty to Trusty
Sweeten the Research | q:Bee Very Careful

## The Great Plateau
Party for the Leafy Spirits
Roast and Relaxation
Cultivating Warm Safflina
The Marita Exchange
The Mission of the Sheikah
Training at Lulu Lake
Great Bridge Repairs
Scars of the Calamity
The Wonders of Chuchu Jelly
Big Moves to Boost Morale
Plum Tuckered Out
Hungry Asceticism
Medicine Is the Best Medicine
Perils of Mount Hylia
A Crucible of Endurance
A Thief in Our Midst
Woodcutter's Discipline
Custom-Made Color
Peace Offering for Hyrule
For the Future of Hyrule
Needs a Splash of...
All the Heartiest Seafood
Off to the Hot Springs | q:Roast and Relaxation
An Eye for Weapons | q:Off to the Hot Springs
Royal Inspection | c:King Rhoam's Training
Facing Powerful Enemies | c:Coliseum: Expert

## All Hyrule, United
Teba's Training Retreat
Daruk's Boot Camp
Extreme Foraging
Parental Support
A Flower Fit for a King
The Royal Treasury
Strategic Fortifications
Feast or Fiction?
A Bird in the Hand
Giving Peace of Mind
The King's Secret Technique
Surveying the Desert Ruins
Expert Cooking Lesson
Fruitful Advice
Inner Power | c:Generational Conflict

## The Future of Hyrule
A Perfectly Honed Body
Mystery Meal for the Merchant
Fuel Up with Plants
Let's Dance
Personal Distractions
Visiting a Special Shop
Research of a Lifetime
Eating a Varied Diet
Tales of the Molten Forge
Remodeling the Flight Range
A Painter's Inspiration
Forest Minuet
The Instructor's Problem
The Lonely Goddess
The Poem-Parsing Traveler
A Secret in Song
Rebuilding Akkala Bridge
An Otherworldly Guardian
The Legendary Blacksmith
Afternoon Tea at Hyrule Castle
A Light in the Dark
Armor that Shines Like a Jewel
Quarry Recruiting
A Gift from the Sky
Opening the Mind's Eye
Strange and Unusual Monsters
Search Party for Parts
No Extreme Too Extreme
Blessing of the Great Fairies
A Strike to Pierce Stone
No Matter the Cost
The Lazy Guards
A Color Seen in a Dream
Road to Rust Research
The Eye That Sees Far
The Pumpkin Hunt
Full Bellies Fight Better
The Master Chef
Zappy 'n' Bouncy
The Korok Who Cried Monster
It's Raining Rupees
There Must Be Rice
Trial of Chaas Qeta
Treats for Patricia
Relieving Meat Fatigue
The Tyrant of the Sand Sea
A King Serves His People
Searching Eventide Island
Fang for Your Buck | q:Mystery Meal for the Merchant
Gerudo Canyon Festival | q:Forest Minuet
Fantastic Flamenco | q:Gerudo Canyon Festival
Goods on the Move in Hyrule! | q:The Legendary Recipe
Gathering the Facts | q:Searching Eventide Island
Right under Our Noses | q:No Extreme Too Extreme
From the Ground Up | c:The Master Kohga Chronicles!
An Unlikely Passion | c:The Master Kohga Chronicles!

## HOPE
The Legendary Recipe
Terrako's Return

## HOPE
# Found in the game's own text (dump v1); unlock conditions not yet known, so gated conservatively.
The Volunteer Army
Teach a Hylian to Fish
Ancient-Material Delivery
Never Enough Fairies
Testing... Testing... One, Two...
Learning from the Best
Preserving for Posterity
Unrelenting Power
Fragmented Memories
Terrako, Enlightened
Terrako, Empowered
Tough as Nails
Tougher than Nails
Slightly Less Tougher than Nails...
Made with Love
To Brighten Her Day
Seething Malice
Hardhearted Malice
Slumbering Malice
Beastly Malice
Reigning Malice
Otherworldly Malice
Explosive Life Force
Nocturnal Life Force
Teeming Life Force
Hidden Life Force
Pursuing Ancient Power
Pursuing Supreme Power
Hyrule Institute of Tactics Research
Fiery Inspiration
Snowbound Cook

## HOPE
# Expansion Pass quests (names start with EX); only active with include_dlc.
EX Seeking Wooden Swords
EX The Squad's Training Retreat
EX A Spear Experiment
EX The Copy Tournament
EX Secret Plans
EX Reunion with the Swordmaster
EX Stamina Woes
EX Break the Obstacles
EX Horsemanship and Horsepower
EX Snow Business
EX Safe Roads, Safe Rides
EX Ride Across Hyrule!
EX The More the Merrier
EX Respect the Elements
EX Harder Than a Guardian?
EX The Ultimate Guardian Showdown!
EX All Enemies Welcome
EX Undeniable Proof
EX Battle-Tested Research
EX Searching for Monster Data
EX Curious Materials
EX Lessons of the Past
EX Regular Maintenance
EX No Detail Too Small
EX A Shocking Run
EX Endless Perseverance
EX Burning Desire
EX Sooga's Swords
EX Taking Aim
EX Secret Wisdom
EX The Right Hand's Hassle
EX Unsung Hero
EX Secret Meetings
EX Monster Troubles
EX A Long-Awaited Battle
EX The Right Hand Strikes Again
EX The Only Option
EX The Relic's Clue
EX The Science of Battle
EX Food for Thought
EX Light as a Feather
EX The Fruits of Ancient-Tech Research
EX A Century of Memories
EX Despicable Distractions
EX A Morsel of Morale
EX All Work and Some Play
EX Peak Condition
EX Perfect Harmony
EX A Royal Gift for Mipha
EX A Royal Gift for Sidon
EX A Royal Gift for Daruk
EX A Royal Gift for Yunobo
EX A Royal Gift for Revali
EX A Royal Gift for Teba
EX A Royal Gift for Urbosa
EX A Royal Gift for Riju
EX The Text of Tomorrow
EX Hasty Recovery
EX Spear Master
EX A Giant Leap
EX Awkward Allies
EX Analysis and Countermeasures
EX Keeping a Promise
EX Survive the Training
EX The Art of Flight
EX Law of the Gerudo
EX Hard Defenses
EX Unstoppable Sidon
EX Goron-Sized Appetites
EX Aim True at the Calamity
EX Sand-Seal Bonding
EX Korok Curiosity
EX The Dazzling Crown
EX Master Kohga's Lightning Training
EX Trial of Kema Kosassa
EX Relic Lessons
EX Violent Obsessions
"""

EXPECTED_COUNT = 458  # distinct quest titles found in the game's own text (381 base + 77 EX)


def _parse() -> list[Quest]:
    quests: list[Quest] = []
    block_gate = ""
    for raw in QUEST_TABLE.strip().splitlines():
        line = raw.strip()
        if not line or (line.startswith("#") and not line.startswith("## ")):
            continue
        if line.startswith("## "):
            block_gate = line[3:].strip()
            continue
        name, _, extras = (p.strip() for p in line.partition(" | "))
        gate = block_gate
        q_pre: list[str] = []
        c_pre: list[str] = []
        for token in filter(None, (t.strip() for t in extras.split(";"))):
            if token.startswith("q:"):
                q_pre.append(token[2:].strip())
            elif token.startswith("c:"):
                c_pre.append(token[2:].strip())
            elif token.startswith("gate="):
                gate = token[5:].strip()
            else:
                raise ValueError(f"bad quest token {token!r} in {raw!r}")
        quests.append(Quest(name, gate, tuple(q_pre), tuple(c_pre)))
    return quests


QUESTS: list[Quest] = _parse()
QUEST_BY_NAME = {q.name: q for q in QUESTS}
# Quests in the game's text with an empty quest row and an empty unlock row (no cost, no reward, no unlock condition;
# every real quest has at least one): cut content that never appears, so never a check. Ids stay registered.
UNUSED_QUESTS = frozenset({"Ancient-Material Delivery", "Seething Malice", "Reigning Malice", "Fiery Inspiration"})
assert len(QUEST_BY_NAME) == len(QUESTS), "duplicate quest names"
