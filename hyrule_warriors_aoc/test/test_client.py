import asyncio
import json
import unittest

from test.bases import WorldTestBase

from ..client.bridge import GameBridge
from ..client.session import Session
from ..data import MISSIONS, WEAPONS


class SessionTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"first_mission": "vanilla", "side_content": ["Weapons", "Challenges", "Quests"], "weapon_check_logic": "after_character"}

    def make_session(self) -> Session:
        # Round-trip through JSON: the real client receives slot_data over the wire.
        return Session(json.loads(json.dumps(self.world.fill_slot_data())))

    def test_only_first_mission_available_at_start(self) -> None:
        self.assertEqual(self.make_session().available_missions(), ["The Battle of Hyrule Field"])

    def test_full_playthrough_reaches_goal(self) -> None:
        session = self.make_session()
        session.unlocked_characters |= {"Mipha", "Daruk", "Revali", "Urbosa"}  # (Calamity Strikes needs them)
        reported = []
        while not session.goal_complete:
            available = session.available_missions()
            self.assertTrue(available)
            location_id = session.on_mission_cleared(available[0])
            self.assertIsNotNone(location_id)
            reported.append(location_id)
        self.assertEqual(len(set(reported)), len(MISSIONS))

    def test_duplicate_reports_are_ignored(self) -> None:
        session = self.make_session()
        self.assertIsNotNone(session.on_mission_cleared("The Battle of Hyrule Field"))
        self.assertIsNone(session.on_mission_cleared("The Battle of Hyrule Field"))
        self.assertIsNone(session.on_mission_cleared("Not A Real Mission"))
        self.assertIsNotNone(session.on_weapon_obtained(WEAPONS[0].name))
        self.assertIsNone(session.on_weapon_obtained(WEAPONS[0].name))

    def test_side_reports(self) -> None:
        session = self.make_session()
        self.assertIsNotNone(session.on_challenge_cleared("Mastering Remote Bombs"))
        self.assertIsNotNone(session.on_quest_completed("Hyrule Swordfighting Academy"))
        self.assertIsNone(session.on_quest_completed("Hyrule Swordfighting Academy"))
        self.assertIsNone(session.on_korok_found("Korok: The Battle of Hyrule Field #1"))  # Koroks are no checks

    def test_reconnect_restores_cleared_state(self) -> None:
        session = self.make_session()
        ids = {session.mission_ids["The Battle of Hyrule Field"], session.weapon_ids[WEAPONS[0].name]}
        self.assertTrue(session.apply_checked_location_ids(ids))
        self.assertIn("The Battle of Hyrule Field", session.cleared_missions)
        self.assertFalse(session.apply_checked_location_ids(ids))

    def test_items_unlock_characters_weapons_and_upgrades(self) -> None:
        session = self.make_session()
        self.assertTrue(session.apply_received_item_names(
            ["Character: Mipha", f"Weapon: {WEAPONS[0].name}", "Heart Container: Link", "Rupee Pouch"]))
        self.assertIn("Mipha", session.unlocked_characters)
        self.assertIn(WEAPONS[0].name, session.unlocked_weapons)
        self.assertEqual(session.upgrades, {"Heart Container: Link": 1})
        self.assertFalse(session.apply_received_item_names(["Character: Mipha", "Rupee Pouch"]))


class SessionExtrasTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"goal": "story_and_boss_rush", "mission_hint_every": 2, "side_content": ["Challenges"],
               "featured_challenge": True}

    def make_session(self) -> Session:
        return Session(json.loads(json.dumps(self.world.fill_slot_data())))

    def test_boss_rush_goal_and_hints_and_tracker(self) -> None:
        session = self.make_session()
        session.unlocked_characters |= {"Mipha", "Daruk", "Revali", "Urbosa"}  # (Calamity Strikes needs them)
        self.assertEqual(session.hints_due(), 0)
        while session.available_missions():
            session.on_mission_cleared(session.available_missions()[0])
        self.assertEqual(session.hints_due(), len(MISSIONS) // 2)
        self.assertEqual(session.hints_due(), 0)
        self.assertFalse(session.goal_complete)
        for boss in session.boss_rush:
            session.on_challenge_cleared(boss)
        self.assertTrue(session.goal_complete)
        html = session.tracker_html()
        self.assertIn("Boss rush 18/18", html)
        self.assertIn("COMPLETE", html)


class NoticeTests(unittest.TestCase):
    def test_game_text_is_plain_short_ascii(self) -> None:
        from ..client.session import game_text
        self.assertEqual(game_text("Zelda\u2019s Bow \u2014 \u00e9"), "Zelda's Bow - ?")
        self.assertLessEqual(len(game_text("x" * 200)), 44)
        self.assertTrue(game_text("x" * 200).endswith("..."))

    def test_notice_shapes_and_batching(self) -> None:
        from ..client.session import batch_notices, make_notice, title_info
        n = make_notice("received", item="Heart Container: Link", player="Alex")
        self.assertEqual(n["text"], "Alex sent Heart Container: Link to you")  # sender and receiver, always
        self.assertEqual(make_notice("sent", item="Hookshot", player="Sam")["text"], "you sent Hookshot to Sam")
        burst = [make_notice("received", item=f"Item {i}") for i in range(7)]
        self.assertEqual(len(batch_notices(burst)), 1)
        self.assertEqual(len(batch_notices(burst[:3])), 3)
        t = title_info(True, slot="Alice", seed="1234", checked=5, total=40)
        self.assertEqual(t["lines"][:2], ["Archipelago: Connected", "Slot: Alice"])
        self.assertEqual(title_info(False)["lines"], ["Archipelago: Not connected"])


class RescueTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"stuck_rescue_minutes": 10}

    def test_rescue_fires_once_per_quiet_spell(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        session.note_activity(1000.0)
        self.assertFalse(session.rescue_due(1000.0 + 599))
        self.assertTrue(session.rescue_due(1000.0 + 600))
        self.assertFalse(session.rescue_due(1000.0 + 1200))
        session.note_activity(5000.0)
        self.assertTrue(session.rescue_due(5000.0 + 600))


class SessionSideGateTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_content": ["Challenges", "Quests"], "challenge_logic": "by_level", "side_missions_per_unlock": 2}

    def test_story_waits_for_side_missions(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        first = "The Battle of Hyrule Field"
        session.on_mission_cleared(session.mission_slots[first])
        slot2 = [s for s, req in session.side_required.items() if req > 0][0]
        self.assertNotIn(session.mission_slots[slot2], session.available_missions())
        for name in list(session.ids["challenge"])[: session.side_required[slot2]]:
            session.on_challenge_cleared(name)
        self.assertIn(session.mission_slots[slot2], session.available_missions())


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_busy_port_does_not_stop_the_client(self) -> None:
        async def on_message(message: dict) -> None:
            pass

        first = GameBridge(on_message, port=0)
        await first.start()
        port = first._server.sockets[0].getsockname()[1]
        second = GameBridge(on_message, port=port)
        with self.assertLogs("AgeOfCalamity", "WARNING"):
            await second.start()  # another client already holds the port: warn, don't raise
        self.assertFalse(second.connected)
        await second.send({"type": "noop"})  # harmless without a game-side hook
        await second.stop()
        await first.stop()

    async def test_round_trip_over_loopback(self) -> None:
        received: list[dict] = []
        got_message = asyncio.Event()

        async def on_message(message: dict) -> None:
            received.append(message)
            got_message.set()

        connected = asyncio.Event()

        async def on_connect() -> None:
            connected.set()

        bridge = GameBridge(on_message, port=0)
        bridge.on_connect = on_connect
        await bridge.start()
        self.addAsyncCleanup(bridge.stop)
        port = bridge._server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        self.addAsyncCleanup(lambda: (writer.close(), None)[1])
        await asyncio.wait_for(connected.wait(), 5)

        # game -> client (including a junk line that must be ignored)
        writer.write(b"not json\n" + b'{"type":"mission_cleared","mission":"Akkala Tower"}\n')
        await writer.drain()
        await asyncio.wait_for(got_message.wait(), 5)
        self.assertEqual(received, [{"type": "mission_cleared", "mission": "Akkala Tower"}])

        # client -> game
        await bridge.send({"type": "hello", "version": 1})
        line = await asyncio.wait_for(reader.readline(), 5)
        self.assertEqual(json.loads(line), {"type": "hello", "version": 1})


class ComboUpgradeTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"combo_upgrades": 5}

    def test_each_item_unlocks_one_level(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual(session.combo_levels()[5], 0)  # Zelda's category, nothing received
        session.apply_received_item_names(["Combo Upgrade: Zelda"] * 2)
        self.assertEqual(session.combo_levels()[5], 2)
        session.apply_received_item_names(["Combo Upgrade: Zelda"] * 9)
        self.assertEqual(session.combo_levels()[5], 4)  # Zelda's line has four quests


class ComboUpgradeSingleTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"combo_upgrades": 1}

    def test_one_item_unlocks_every_link_line(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        session.apply_received_item_names(["Combo Upgrade: Link"])
        levels = session.combo_levels()
        self.assertEqual([levels[c] for c in (0, 1, 2)], [5, 5, 5])
        self.assertEqual(levels[5], 0)


class ChallengeUnlockTests(WorldTestBase):
    """The client rewrites the game's challenge rows to match challenge_logic (vanilla rows need story missions in
    vanilla order, other challenges and quests, which a shuffled seed's logic does not expect)."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_unlocks": "game_rules", "side_content": ["Challenges"], "challenge_logic": "after_story"}

    def make_session(self, every_hero: bool = True) -> Session:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        if every_hero:
            session.apply_received_item_names([f"Character: {c}" for c in session.all_characters])
        return session

    def test_after_story_keeps_only_vanilla_story_prerequisites(self) -> None:
        unlocks = self.make_session().challenge_unlocks()
        self.assertEqual(unlocks[158], (2,))  # Mastering Remote Bombs: Road to the Ancient Lab
        self.assertEqual(unlocks[102], (13,))  # Anti-Flame Training: II drops Anti-Flame Training: I
        self.assertEqual(unlocks[186], (15,))  # Trial of the Ancients (Destroy the Yiga Clan! part 2): quests dropped
        self.assertEqual(unlocks[167], (28,))  # Hair-Width Trial: Expert+ needed only a challenge: the final mission
        self.assertNotIn(30, unlocks)  # Meditative Training is open from the start in vanilla
        self.assertTrue(all(r <= 28 for needs in unlocks.values() for r in needs))

    def test_challenge_waits_for_its_forced_heroes(self) -> None:
        from ..data_save import MISSION_RECORD_IDS
        session = self.make_session(every_hero=False)
        session.unlocked_characters = {"Daruk"}
        self.assertEqual(session.challenge_unlocks()[136], (136,))  # Link-only: closed until Link (plays broken)
        bows = MISSION_RECORD_IDS["Zelda's Training: Bows"][0]
        self.assertEqual(session.challenge_unlocks().get(bows), (bows,))
        session.unlocked_characters |= {"Link"}
        self.assertEqual(session.challenge_unlocks()[136], (1, 6))


class ChallengeUnlockByLevelTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_unlocks": "game_rules", "side_content": ["Challenges"], "challenge_logic": "by_level", "mission_order": "shuffle_all",
               "locked_features": []}

    def test_rows_require_the_logic_gate(self) -> None:
        from ..data_save import MISSION_RECORD_IDS
        from ..rules import challenge_requirements
        from ..regions import POST_STORY_EVENT, STORY_EVENT, cleared_event
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        session.apply_received_item_names([f"Character: {c}" for c in session.all_characters])
        unlocks = session.challenge_unlocks()
        self.assertEqual(unlocks[158], (1,))  # Mastering Remote Bombs: The Battle of Hyrule Field
        for name in self.world.active_challenges:
            record = MISSION_RECORD_IDS[name][0]
            if record not in unlocks:
                continue
            gate = challenge_requirements(self.world, name)[0]
            if gate not in (STORY_EVENT, POST_STORY_EVENT):
                story = next(m for m in MISSION_RECORD_IDS if cleared_event(m) == gate)
                self.assertEqual(unlocks[record], (max(MISSION_RECORD_IDS[story]),), name)


class RuneShuffleTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_content": ["Challenges"], "sheikah_runes": "shuffled"}

    def test_runes_are_items_and_gate_their_challenges(self) -> None:
        from ..items import rune_item
        pool = {i.name for i in self.multiworld.get_items() if i.player == self.player}
        self.assertTrue({rune_item(r) for r in ("Cryonis", "Magnesis", "Stasis")} <= pool)
        self.assertNotIn(rune_item("Remote Bombs"), pool)  # always on (the Slate)
        # Built by hand: collect_all_but would also pick up a rune the story pacing already placed on a location.
        from BaseClasses import CollectionState
        state = CollectionState(self.multiworld)
        items = self.multiworld.itempool + [loc.item for loc in self.multiworld.get_locations() if loc.item]
        for item in items:
            if item.player == self.player and item.name != "Rune: Stasis":
                state.collect(item, True)
        location = self.world.get_location("Challenge: Mastering Stasis")
        self.assertFalse(location.access_rule(state))
        state.collect(self.world.create_item("Rune: Stasis"), True)
        self.assertTrue(location.access_rule(state))

    def test_client_enforces_three_runes_and_keeps_the_slate(self) -> None:
        names = {i.name for i in self.multiworld.itempool}
        self.assertNotIn("Rune: Remote Bombs", names)  # always on: it is the Sheikah Slate
        self.assertTrue({"Rune: Cryonis", "Rune: Magnesis", "Rune: Stasis"} <= names)
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual(session.rune_flags(),
                         {"Remote Bombs": True, "Cryonis": False, "Magnesis": False, "Stasis": False})
        session.apply_received_item_names(["Rune: Stasis", "Rune: Cryonis"])
        self.assertEqual(session.rune_flags(),
                         {"Remote Bombs": True, "Cryonis": True, "Magnesis": False, "Stasis": True})

    def test_old_seeds_enforce_magnesis_and_stasis_only(self) -> None:
        data = json.loads(json.dumps(self.world.fill_slot_data()))
        del data["rune_items"]  # a seed from before 0.9.58
        session = Session(data)
        session.apply_received_item_names(["Rune: Stasis", "Rune: Remote Bombs"])
        self.assertEqual(session.rune_flags(), {"Magnesis": False, "Stasis": True})


class RuneVanillaTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"sheikah_runes": "vanilla"}

    def test_no_rune_items_and_client_leaves_runes_alone(self) -> None:
        pool = {i.name for i in self.multiworld.get_items() if i.player == self.player}
        self.assertFalse({n for n in pool if n.startswith("Rune: ")})
        self.assertEqual(Session(json.loads(json.dumps(self.world.fill_slot_data()))).rune_flags(), {})


class MissionUnlockItemTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"first_mission": "vanilla", "mission_unlocks": "items", "starting_mission_unlocks": 1, "mission_order": "shuffle_all",
               "side_content": ["Challenges", "Quests"]}

    def test_every_mission_but_the_first_has_an_unlock_item(self) -> None:
        names = [i.name for i in self.multiworld.get_items() if i.player == self.player]
        names += [i.name for i in self.multiworld.precollected_items[self.player]]
        unlocks = sorted(n for n in names if n.startswith("Unlock: "))
        self.assertEqual(unlocks, sorted(f"Unlock: {m.name}" for m in MISSIONS[1:]  # (these open by themselves)
                                         if m.name not in ("Calamity Strikes", "Water and Fire", "Air and Lightning")))
        self.assertEqual(self.world.mission_order, [m.name for m in MISSIONS])  # mission_order is ignored
        self.assertEqual(len(self.world.starting_unlocks), 1)
        start = self.world.starting_unlocks[0]
        self.assertLessEqual(next(m.chapter for m in MISSIONS if m.name == start), 2)

    def test_a_mission_opens_with_its_unlock_item_alone(self) -> None:
        from BaseClasses import CollectionState
        locked = next(m.name for m in MISSIONS[1:] if m.name not in self.world.starting_unlocks)
        state = CollectionState(self.multiworld)
        start = self.world.get_entrance(f"Start {locked}")
        self.assertFalse(start.access_rule(state))
        state.collect(self.world.create_item(f"Unlock: {locked}"), True)
        self.assertTrue(start.access_rule(state))

    def test_client_opens_missions_by_unlock_items(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual(session.available_missions(), ["The Battle of Hyrule Field"])
        late = "The Future of Hyrule"
        session.apply_received_item_names([f"Unlock: {late}"])
        self.assertEqual(session.available_missions(), ["The Battle of Hyrule Field", late])
        session.on_mission_cleared(late)
        self.assertEqual(session.available_missions(), ["The Battle of Hyrule Field"])


class DlcVanillaTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"include_dlc": False, "side_content": ["Challenges"]}

    def test_client_leaves_expansion_pass_challenges_alone(self) -> None:
        from ..data_challenges import CHALLENGE_BY_NAME
        from ..data_save import MISSION_RECORD_IDS
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        ex_records = {MISSION_RECORD_IDS[n][0] for n, c in CHALLENGE_BY_NAME.items() if c.is_ex and n in MISSION_RECORD_IDS}
        unlocks = session.challenge_unlocks()
        self.assertTrue(unlocks)
        self.assertFalse(ex_records & set(unlocks))
        self.assertFalse({i.name for i in self.multiworld.get_items() if i.player == self.player}
                         & {"Character: Purah & Robbie", "Character: Sooga"})


class HeroBonusTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"heart_containers": 2, "special_gauge_upgrades": 1}

    def test_hearts_and_gauges_follow_received_items(self) -> None:
        from ..data_save import HERO_SLOTS
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual(set(session.hero_bonus("Heart Container").values()), {0})
        session.apply_received_item_names(["Heart Container: Mipha"] * 3 + ["Special Gauge Upgrade: Mipha"])
        self.assertEqual(session.hero_bonus("Heart Container")[HERO_SLOTS["Mipha"]], 3)  # both copies = vanilla +3
        self.assertEqual(session.hero_bonus("Special Gauge Upgrade")[HERO_SLOTS["Mipha"]], 2)  # 1 of 1 = vanilla +2
        self.assertNotIn(HERO_SLOTS["Sooga"], session.hero_bonus("Heart Container"))  # DLC off: left vanilla


class ProfileRewardTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"enhanced_abilities": 1, "weapon_capacity_upgrades": 4}

    def test_abilities_and_capacity_follow_received_items(self) -> None:
        from ..data_save import ABILITY_FLAGS, WEAPON_CAPACITY_LEVEL
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        values = session.profile_rewards()
        self.assertEqual(values[WEAPON_CAPACITY_LEVEL], 0)
        self.assertEqual(values[ABILITY_FLAGS + 8], 0)  # Mipha
        session.apply_received_item_names(["Enhanced Ability: Link", "Enhanced Ability: Mipha"] + ["Progressive Weapon Capacity"] * 2)
        values = session.profile_rewards()
        self.assertEqual(values[WEAPON_CAPACITY_LEVEL], 2)
        self.assertEqual(values[ABILITY_FLAGS + 8], 1)
        self.assertEqual([values[ABILITY_FLAGS + c] for c in (0, 1, 2)], [1, 1, 1])  # one item = all of Link's share
        self.assertNotIn(ABILITY_FLAGS + 27, values)  # Sooga (DLC off) stays vanilla


class QuestRewardDataTests(unittest.TestCase):
    def test_reward_quests_exist_and_are_base_game(self) -> None:
        from ..data_quests import QUEST_BY_NAME
        from ..data_rewards import HERO_QUESTS, OPEN_SERVICE_QUESTS, REWARD_GROUPS
        from ..data_save import QUEST_STATE_IDS
        seen = set()
        for group in REWARD_GROUPS:
            self.assertTrue(group.known, group.item)
            if group.kind == "store":
                self.assertEqual(len(group.writes), len(group.quests), group.item)
            for quest in group.quests:
                self.assertIn(quest, QUEST_BY_NAME)
                self.assertIn(quest, QUEST_STATE_IDS)
                self.assertEqual(QUEST_BY_NAME[quest].is_ex, group.dlc, quest)
                self.assertNotIn(quest, seen)
                seen.add(quest)
        for quest in (*OPEN_SERVICE_QUESTS, *HERO_QUESTS):
            self.assertIn(quest, QUEST_STATE_IDS)
            self.assertNotIn(quest, seen)

    def test_share_rule(self) -> None:
        from ..data_rewards import REWARD_BY_ITEM, canonical, given_quests
        hot = REWARD_BY_ITEM[canonical("Progressive Hot Springs")]  # 3 quests
        self.assertEqual([given_quests(hot, k, 3) for k in range(5)], [0, 1, 2, 3, 3])
        self.assertEqual([given_quests(hot, k, 1) for k in range(2)], [0, 3])  # one copy = all three
        self.assertEqual([given_quests(hot, k, 2) for k in range(3)], [0, 2, 3])


class QuestRewardTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    # old item names on purpose: YAMLs written before the 0.9.52 rename must keep working
    options = {"side_unlocks": "game_rules", "side_content": ["Quests"], "quest_reward_items": {"Progressive Hot Springs": 3,
                                                                  "Progressive Shop Unlock": 4,
                                                                  "Progressive Treasure Detector": 2}}

    def test_items_in_pool_and_slot_data(self) -> None:
        names = [i.name for i in self.multiworld.get_items() if i.player == self.player]
        names += [i.name for i in self.multiworld.precollected_items[self.player]]
        from ..data_rewards import canonical
        hot, detector, seals = map(canonical, ("Progressive Hot Springs", "Progressive Treasure Detector",
                                               "Progressive Seal Slot"))
        self.assertEqual(names.count(hot), 3)
        self.assertNotIn("Progressive Hot Springs", names)  # new seeds use the new names
        self.assertEqual(names.count("Progressive Shop Unlock"), 4)
        self.assertNotIn("Progressive Stable Unlock", names)
        self.assertEqual(self.world.fill_slot_data()["quest_reward_items"],
                         {hot: 3, "Progressive Shop Unlock": 4, detector: 2,
                          seals: 2, "Feature: Cooking": 1,
                          "Feature: Terrako Guardian": 1})

    def test_shop_quests_are_checks_and_their_service_needs_the_item(self) -> None:
        from ..data_rewards import OPEN_SERVICE_QUESTS, REWARD_BY_ITEM
        shops = REWARD_BY_ITEM["Progressive Shop Unlock"].quests
        self.assertTrue(set(shops) <= self.world.checked_quests)  # buying a shop quest is its check
        self.assertFalse(set(OPEN_SERVICE_QUESTS) & self.world.checked_quests)
        self.assertNotIn("Brawny Blacksmiths", self.world.checked_quests)  # Smithy open from the start (default)
        # Relief for Soldier Stress (8th shop quest) counts as done in game only with all 4 copies.
        state = self.multiworld.get_all_state(False)
        rule = self.world.get_location("Event: Quest Relief for Soldier Stress").access_rule
        buy = self.world.get_location("Quest: Relief for Soldier Stress").access_rule
        for k in range(4):
            state.prog_items[self.player]["Progressive Shop Unlock"] = k
            self.assertFalse(rule(state), k)
            self.assertTrue(buy(state), k)  # buyable without the item
        state.prog_items[self.player]["Progressive Shop Unlock"] = 4
        self.assertTrue(rule(state))

    def test_client_forces_rewards_and_services(self) -> None:
        from ..data_rewards import PROFILE
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        writes = session.reward_writes()
        self.assertEqual(writes[(PROFILE, 0x79E)], 0)
        self.assertEqual((writes[(PROFILE, 0xC7D)], writes[(PROFILE, 0xC7E)]), (0, 0))
        self.assertNotIn((PROFILE, 0x79F), writes)  # Tailored Clothes not in this seed: vanilla
        states = session.quest_states()
        self.assertEqual(states["Entrance Test"], 3)
        self.assertEqual(states["Brawny Blacksmiths"], 3)  # Smithy open from the start (weapon_fusion off)
        self.assertNotIn("Brilliance for the Boutique", states)
        self.assertNotIn("Wedding Worry", states)  # stables vanilla here
        session.on_quest_completed("Brilliance for the Boutique")
        session.on_quest_completed("Shop-Quick Store")
        self.assertEqual(session.quest_states()["Brilliance for the Boutique"], 1)  # bought, no item: closed again
        session.apply_received_item_names(["Progressive Hot Springs"] * 2
                                          + ["Progressive Shop Unlock", "Progressive Treasure Detector"])
        writes = session.reward_writes()
        self.assertEqual(writes[(PROFILE, 0x79E)], 2)
        self.assertEqual((writes[(PROFILE, 0xC7D)], writes[(PROFILE, 0xC7E)]), (1, 0))
        states = session.quest_states()
        # 1 of 4 copies = 2 of 8 quests: the bought 1st opens; the 2nd isn't bought; the bought 3rd waits for its share
        self.assertEqual((states["Brilliance for the Boutique"], states.get("Gotta Have a Sign"), states["Shop-Quick Store"]),
                         (3, None, 1))
        self.assertIn("Brilliance for the Boutique", session.held_quests())


class QuestRewardVanillaTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_unlocks": "game_rules", "side_content": ["Quests"], "quest_reward_items": {}, "weapon_fusion": False, "seal_slot_upgrades": 0,
               "locked_features": []}

    def test_no_items_and_client_leaves_rewards_alone(self) -> None:
        from ..data_rewards import REWARD_BY_ITEM
        names = {i.name for i in self.multiworld.get_items() if i.player == self.player}
        self.assertFalse(names & set(REWARD_BY_ITEM))
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual(session.reward_writes(), {})
        self.assertEqual(set(session.quest_states()), {"Brawny Blacksmiths", "Entrance Test"})
        self.assertIn("Brilliance for the Boutique", self.world.checked_quests)


class MissionRewardShuffleTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"mission_rewards": "shuffled"}

    def test_shuffled_rewards_are_a_permutation_of_base_missions(self) -> None:
        from ..data_mission_rewards import vanilla_row
        plan = json.loads(json.dumps(self.world.fill_slot_data()))["mission_rewards"]
        self.assertEqual(plan["mode"], 1)
        targets = sorted(int(r) for r in plan["map"])
        self.assertEqual(sorted(plan["map"].values()), targets)  # every reward set is used exactly once
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        rows = session.mission_reward_rows()
        self.assertEqual(sorted(rows), targets)
        for r, src in plan["map"].items():
            self.assertEqual(rows[int(r)], vanilla_row(src))


class MissionRewardNoneTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"mission_rewards": "none"}

    def test_no_reward_counts(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        rows = session.mission_reward_rows()
        self.assertTrue(rows)
        self.assertTrue(all(not any(row[0x04:0x20]) for row in rows.values()))


class MissionRewardVanillaTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"

    def test_vanilla_leaves_table_alone(self) -> None:
        self.assertEqual(Session(json.loads(json.dumps(self.world.fill_slot_data()))).mission_reward_rows(), {})


class QuestUnlockTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_unlocks": "game_rules", "side_content": ["Quests"], "quest_reward_items": {"Progressive Divine Beast Upgrade": 4}}

    def test_unlock_quests_stay_checks_gated_by_their_item(self) -> None:
        quest = "Surveying the Volcano"  # 2nd Divine Beast quest: needs 2 copies
        self.assertIn(quest, self.world.checked_quests)
        self.assertIn("Progressive Divine Beast Upgrade", self.world.reward_progression)
        rule = self.world.get_location(f"Quest: {quest}").access_rule
        state = self.multiworld.get_all_state(False)  # everything, then only the unlock item's count varies
        state.prog_items[self.player]["Progressive Divine Beast Upgrade"] = 1
        self.assertFalse(rule(state))
        state.prog_items[self.player]["Progressive Divine Beast Upgrade"] = 2
        self.assertTrue(rule(state))

    def test_client_hides_then_opens(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        states = session.quest_states()
        self.assertEqual(states["Regulating the Reservoir"], -1)
        session.apply_received_item_names(["Progressive Divine Beast Upgrade"])
        states = session.quest_states()
        self.assertEqual((states["Regulating the Reservoir"], states["Surveying the Volcano"]), (2, -1))



class FeatureItemTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_unlocks": "game_rules", "side_content": ["Quests", "Challenges"], "challenge_logic": "by_level",
               "locked_features": ["Cooking", "Shops", "Fairy Fountains", "Terrako Guardian"], "weapon_fusion": True}

    def test_features_drive_quests_and_challenges(self) -> None:
        w = self.world
        self.assertEqual(w.unlock_quests["Hot Meals in a Pot"], "Feature: Cooking")
        self.assertEqual(w.item_quests["Brilliance for the Boutique"], "Feature: Shops")
        self.assertEqual(w.item_quests["Brawny Blacksmiths"], "Weapon Fusion")
        self.assertEqual(w.group_copies["Progressive Shop Unlock"], 0)
        # A cooking quest the game only shows after Hot Meals in a Pot needs Feature: Cooking too.
        state = self.multiworld.get_all_state(False)
        rule = w.get_location("Event: Quest Stumped by Shrooms").access_rule
        self.assertTrue(rule(state))
        state.prog_items[self.player]["Feature: Cooking"] = 0
        self.assertFalse(rule(state))
        session = Session(json.loads(json.dumps(w.fill_slot_data())))
        states = session.quest_states()
        self.assertEqual(states["Hot Meals in a Pot"], -1)
        self.assertNotIn("Brilliance for the Boutique", states)  # buyable (its check); the shop waits for the item
        fairy = session.challenge_unlocks()
        session.apply_received_item_names(["Feature: Cooking", "Feature: Shops", "Weapon Fusion", "Feature: Fairy Fountains"])
        session.on_quest_completed("Gotta Have a Sign")
        session.on_quest_completed("Brawny Blacksmiths")
        states = session.quest_states()
        self.assertEqual((states["Hot Meals in a Pot"], states["Gotta Have a Sign"], states["Brawny Blacksmiths"]), (2, 3, 3))
        from ..data_save import MISSION_RECORD_IDS
        record = MISSION_RECORD_IDS["Fairy Fountain: Battlefield"][0]
        self.assertNotEqual(fairy.get(record), session.challenge_unlocks().get(record))  # opened by the item

    def test_seal_slots_drive_seal_removal(self) -> None:
        from ..data_rewards import FLAGS
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual(session.reward_writes()[(FLAGS, 0x1A04)], 0)
        session.apply_received_item_names(["Progressive Seal Slot"])
        self.assertEqual(session.reward_writes()[(FLAGS, 0x1A04)], 1)


class DifficultyGoalTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"goal_difficulty": "hard"}

    def test_goal_waits_for_hard_clears(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual(session.goal_difficulty, 3)
        for m in session.mission_ids:
            session.cleared_missions.add(m)
        self.assertFalse(session.goal_complete)
        session.difficulty_cleared = set(session.mission_ids)
        self.assertTrue(session.goal_complete)


class ShortGoalTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"goal_story_missions": 5}

    def test_goal_after_five_story_clears(self) -> None:
        from ..regions import STORY_EVENT, VICTORY_EVENT, cleared_event
        state = self.multiworld.get_all_state(False)
        missions = list(self.world.mission_order)
        for m in missions:
            state.prog_items[self.player][cleared_event(m)] = 0
        state.prog_items[self.player][VICTORY_EVENT] = 0
        state.prog_items[self.player][STORY_EVENT] = 0
        finish = self.world.get_entrance("Finish All Main Missions").access_rule
        story = self.world.get_entrance("Finish The Story").access_rule
        for m in missions[:4]:
            state.prog_items[self.player][cleared_event(m)] = 1
        self.assertFalse(finish(state))
        state.prog_items[self.player][cleared_event(missions[4])] = 1
        self.assertTrue(finish(state))
        self.assertFalse(story(state))  # post-story content still waits for all 20
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        session.cleared_missions.update(missions[:5])
        self.assertTrue(session.goal_complete)


class ChallengeGoalTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_content": ["Challenges"], "goal_story_missions": 3, "goal_challenges": 2, "sheikah_runes": "start_with_all"}

    def test_story_and_challenge_counts(self) -> None:
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual((session.goal_story_missions, session.goal_challenges), (3, 2))
        session.cleared_missions.update(list(session.mission_ids)[:3])
        self.assertFalse(session.goal_complete)
        session.cleared_any = set(sorted(session.goal_challenge_pool)[:2])
        self.assertTrue(session.goal_complete)

    def test_all_runes_from_the_start(self) -> None:
        names = {i.name for i in self.multiworld.get_items() if i.player == self.player}
        self.assertFalse({n for n in names if n.startswith("Rune: ")})
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertEqual(session.rune_flags(), {"Remote Bombs": True, "Cryonis": True, "Magnesis": True, "Stasis": True})


class PostStoryUnlockTests(WorldTestBase):
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_unlocks": "game_rules", "side_content": ["Challenges", "Quests"], "post_story_unlock": 6, "quest_reward_items": {}}

    def test_post_story_content_opens_after_six_clears(self) -> None:
        from ..data_challenges import challenge_gate
        from ..data_save import MISSION_RECORD_IDS
        from ..regions import POST_STORY_EVENT, cleared_event
        state = self.multiworld.get_all_state(False)
        missions = list(self.world.mission_order)
        for m in missions:
            state.prog_items[self.player][cleared_event(m)] = 1 if m in missions[:6] else 0
        self.assertTrue(self.world.get_entrance("Open Post-Story Content").access_rule(state))
        state.prog_items[self.player][cleared_event(missions[5])] = 0
        self.assertFalse(self.world.get_entrance("Open Post-Story Content").access_rule(state))
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        session.apply_received_item_names([f"Character: {c}" for c in session.all_characters])
        post = next(c for c in self.world.active_challenges if not challenge_gate(c, False, False)
                    and MISSION_RECORD_IDS[c][0] in session.challenge_unlocks())
        record = MISSION_RECORD_IDS[post][0]
        self.assertNotEqual(session.challenge_unlocks()[record], ())
        session.cleared_missions.update(missions[:6])
        self.assertEqual(session.challenge_unlocks()[record], ())  # opened early
        quest = session.post_story_quests[0]
        self.assertEqual(session.quest_states().get(quest), 2)


class CatchUpLevelTests(unittest.TestCase):
    """catch_up_levels: a newly received hero joins at the level of your lowest-level hero, never lower than its own."""

    def sync(self, levels: dict[str, int], starting: list[str], received: list[str], caught: list[str]) -> list[str]:
        from types import SimpleNamespace
        from ..client.ap_client import AoCContext

        class Live:
            def grant_hero(self, hero): return False
            def revoke_hero(self, hero): return False
            def hero_level(self, hero): return levels.get(hero, 1)
            def set_level(self, hero, level):
                if levels.get(hero, 1) >= level:
                    return False
                levels[hero] = level
                return True
            def raise_levels(self, heroes, level): return []

        notes = []
        ctx = SimpleNamespace(
            session=SimpleNamespace(unlocked_characters=set(starting) | set(received), story_party_free=True,
                                    include_dlc=True, pace={"catch_up": True}, starting_characters=starting,
                                    min_level=1),
            live=Live(),
            delivery=SimpleNamespace(state={"caught_up": list(caught)}, note=notes.extend, save_state=lambda: None))
        AoCContext._sync_heroes(ctx)
        self.assertEqual(sorted(ctx.delivery.state["caught_up"]), sorted(set(caught) | set(starting) | set(received)))
        return notes

    def test_new_hero_joins_at_lowest_level(self) -> None:
        levels = {"Link": 20, "Zelda": 12, "Impa": 15, "Mipha": 1}
        notes = self.sync(levels, ["Link", "Zelda", "Impa"], ["Mipha"], [])
        self.assertEqual(levels["Mipha"], 12)
        self.assertIn("Mipha caught up to level 12", notes)

    def test_never_lowers_and_only_once(self) -> None:
        levels = {"Link": 20, "Zelda": 12, "Daruk": 30, "Mipha": 5}
        self.sync(levels, ["Link", "Zelda"], ["Daruk"], [])
        self.assertEqual(levels["Daruk"], 30)  # already above the lowest hero
        levels["Zelda"] = 25
        self.sync(levels, ["Link", "Zelda"], ["Daruk", "Mipha"], ["Daruk"])
        self.assertEqual(levels["Mipha"], 20)  # lowest now Link at 20 (Daruk 30, Zelda 25)
        levels["Link"] = 40
        self.sync(levels, ["Link", "Zelda"], ["Daruk", "Mipha"], ["Daruk", "Mipha"])
        self.assertEqual(levels["Mipha"], 20)  # caught up once: later level-ups of others don't move it


class FreeHintTests(unittest.IsolatedAsyncioTestCase):
    """mission_hint_every: hints already given survive a client restart (every reconnect reports all clears again)."""

    async def test_hints_not_given_again_after_restart(self) -> None:
        from types import SimpleNamespace
        from ..client.ap_client import AoCContext
        from ..client.session import Session

        sent = []

        async def send_msgs(msgs):
            sent.extend(msgs)

        session = SimpleNamespace(hint_every=2, cleared_missions={"a", "b", "c", "d"}, hints_given=0)
        session.hints_due = lambda: Session.hints_due(session)
        state = {"hints_given": 2}
        ctx = SimpleNamespace(session=session, send_msgs=send_msgs, missing_locations={1, 2, 3}, locations_checked=set(),
                              delivery=SimpleNamespace(state=state, save_state=lambda: None))
        await AoCContext._grant_free_hints(ctx)  # restart: 4 clears = 2 hints, both given before
        self.assertEqual(sent, [])
        session.cleared_missions |= {"e", "f"}
        await AoCContext._grant_free_hints(ctx)
        self.assertEqual(len(sent), 1)
        self.assertEqual(state["hints_given"], 3)


class RewardRenameTests(unittest.TestCase):
    """Rooms generated before the 0.9.52 rename send old reward names (slot data and items): both still work."""

    def test_old_room_names(self) -> None:
        from ..data_rewards import ITEM_RENAMES, REWARD_BY_ITEM, canonical
        self.assertTrue(all(new in REWARD_BY_ITEM for new in ITEM_RENAMES.values()))
        self.assertEqual(canonical("Inner Knowing"), "Special Gauge Recovery Up (Inner Knowing)")
        self.assertEqual(canonical("Progressive Shop Unlock"), "Progressive Shop Unlock")  # unchanged names pass
        self.assertEqual(len(set(ITEM_RENAMES.values())), len(ITEM_RENAMES))


class RandomSideUnlockTests(WorldTestBase):
    """side_unlocks shuffled (default): challenges and quests open after random completion counts."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_content": ["Challenges", "Quests"], "quest_reward_items": {}}

    def test_plan_opens_a_few_then_two_to_four_per_completion(self) -> None:
        from collections import Counter
        from ..world import RANDOM_SIDE_MIN_EACH, RANDOM_SIDE_START, RANDOM_SIDE_STEP
        w = self.world
        self.assertEqual(set(w.challenge_open_at), set(w.active_challenges))  # (post-story mixed in by default)
        at = list(w.challenge_open_at.values()) + list(w.quest_open_at.values())
        per = Counter(at)
        self.assertGreaterEqual(per[0], RANDOM_SIDE_START)
        self.assertGreaterEqual(sum(v == 0 for v in w.challenge_open_at.values()), RANDOM_SIDE_MIN_EACH)
        self.assertGreaterEqual(sum(v == 0 for v in w.quest_open_at.values()), RANDOM_SIDE_MIN_EACH)
        last = max(at)
        self.assertEqual(sorted(per), list(range(last + 1)))  # every completion opens something
        for k in range(1, last):
            self.assertTrue(RANDOM_SIDE_STEP[0] <= per[k] <= RANDOM_SIDE_STEP[1])

    def test_logic_needs_the_completion_count(self) -> None:
        from ..data_challenges import CHALLENGE_BY_NAME
        from ..data import RUNE_CHALLENGES
        w = self.world
        name, opens = next((c, t) for c, t in sorted(w.challenge_open_at.items(), key=lambda x: -x[1])
                           if t and not CHALLENGE_BY_NAME[c].required_characters and c not in RUNE_CHALLENGES)
        from ..world import COMPLETIONS
        state = self.multiworld.get_all_state(False)
        self.assertGreaterEqual(state.prog_items[self.player][COMPLETIONS], opens)  # collect keeps the counter
        state.prog_items[self.player][COMPLETIONS] = opens - 1
        rule = w.get_location(f"Event: Challenge {name}").access_rule
        self.assertFalse(rule(state))
        state.prog_items[self.player][COMPLETIONS] = opens
        self.assertTrue(rule(state))

    def test_client_opens_by_completions(self) -> None:
        from ..data_challenges import CHALLENGE_BY_NAME
        from ..data_save import MISSION_RECORD_IDS
        from ..data_rewards import OPEN_SERVICE_QUESTS
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        self.assertTrue(session.side_random)
        session.apply_received_item_names([f"Character: {c}" for c in session.all_characters])
        name, opens = next((c, t) for c, t in session.challenge_open_at.items() if t >= 3
                           and MISSION_RECORD_IDS[c][0] in session.challenge_unlocks())
        record = MISSION_RECORD_IDS[name][0]
        quest = next(q for q, t in session.quest_open_at.items() if t >= opens and q not in OPEN_SERVICE_QUESTS)
        self.assertEqual(session.challenge_unlocks()[record], (record,))  # closed: needs its own clear
        self.assertEqual(session.quest_states()[quest], -1)
        from ..data_save import QUEST_STATE_IDS
        self.assertEqual(session.quest_rows()[quest], ((), (QUEST_STATE_IDS[quest],)))  # needs itself: never opens
        self.assertNotIn(name, session.side_opened())
        names = sorted(session.completion_names - {name, quest})
        session.game_done = set(names[:opens])
        self.assertEqual(session.completions, opens)
        self.assertEqual(session.challenge_unlocks()[record], ())
        self.assertIn(name, session.side_opened())
        session.game_done = set(names[:session.quest_open_at[quest]])
        self.assertEqual(session.quest_states()[quest], 2)
        self.assertEqual(session.quest_rows()[quest], ((), ()))  # the game's row needs nothing now
        self.assertTrue(CHALLENGE_BY_NAME[name])


class RuneHintTests(WorldTestBase):
    """Shuffled rune items are start hints (free hints for everyone from the start)."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"sheikah_runes": "shuffled"}

    def test_runes_are_start_hints(self) -> None:
        from ..data import ITEM_RUNES
        from ..items import rune_item
        self.assertTrue({rune_item(r) for r in ITEM_RUNES} <= self.world.options.start_hints.value)
        self.assertNotIn("Rune: Remote Bombs", self.world.options.start_hints.value)


class EffectAuditTests(unittest.TestCase):
    """The probe re-checks client effects at 20 s, 5 min and after the next mission clear."""

    def test_stages_and_announcements(self) -> None:
        import tempfile
        import time as _time
        from pathlib import Path
        from ..client import live_hook
        from ..client.probe import Probe
        with tempfile.TemporaryDirectory() as folder:
            probe = Probe(None, Path(folder))
            state = {"ok": True}
            live_hook.EXPECTATIONS.append((_time.time() - 25, "Weapon XP Gift", lambda: (state["ok"], "level 3"),
                                           {"hero": "Urbosa"}))
            probe.watch_effects()
            findings = [json.loads(l) for l in (Path(folder) / "findings.jsonl").read_text().splitlines()]
            self.assertEqual([(f["stage"], f["ok"]) for f in findings], [("20s", True)])
            self.assertEqual(probe.announcements, [])  # a 20 s success stays quiet
            state["ok"] = False
            probe.watch_effects(mission_cleared=True)
            probe._effects[0]["mission_due"] = 0
            probe.watch_effects()
            self.assertIn("undone", probe.announcements[-1])
            self.assertEqual(probe._effects, [])  # done after the mission check


class FirstMissionTests(WorldTestBase):
    """first_mission random_early (default): a chapter 1-2 mission first; Hyrule Field gets an unlock item."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"mission_unlocks": "items", "starting_mission_unlocks": 2}

    def test_hyrule_field_first_then_a_random_early_mission(self) -> None:
        order = self.world.mission_order
        self.assertEqual(order[0], "The Battle of Hyrule Field")  # cleared in the starter save
        self.assertLessEqual(next(m.chapter for m in MISSIONS if m.name == order[1]), 2)
        self.assertEqual(self.world.starting_unlocks[0], order[1])  # the first mission you play is open
        self.assertEqual(len(self.world.starting_unlocks), 2)
        data = self.world.fill_slot_data()
        self.assertTrue(data["starter_save"])
        session = Session(json.loads(json.dumps(data)))
        session.apply_received_item_names([f"Unlock: {m}" for m in self.world.starting_unlocks])
        self.assertIn(order[1], session.available_missions())


class StarterSaveTests(unittest.TestCase):
    """The starter save template and the rules for installing it."""

    def test_template_is_a_fresh_save(self) -> None:
        from ..client import starter_save
        from ..client.savefile import cleared_missions, hero_unlocked
        data = starter_save.template()
        self.assertEqual(cleared_missions(data), {"The Battle of Hyrule Field"})  # else the game replays the opening
        self.assertTrue(starter_save.is_fresh(data))
        from ..client.savefile import hero_level
        from .. import data_save as S
        self.assertFalse(any(hero_unlocked(data, h) for h in S.HERO_SLOTS))  # everyone locked
        self.assertTrue(all(hero_level(data, h) == 1 for h in S.HERO_SLOTS))  # everyone level 1
        from ..client.savefile import completed_quests
        self.assertEqual(completed_quests(data), set())  # a fresh game's quests (none carried over)
        prepared = starter_save.prepare(["Revali", "Link", "Daruk", "Riju"],
                                        ["Mipha, the Zora Princess", "The Battle of Hyrule Field"])
        self.assertEqual({h for h in S.HERO_SLOTS if hero_unlocked(prepared, h)}, {"Revali", "Link", "Daruk", "Riju"})
        from .. import data_save as L
        record = L.MISSION_RECORD_IDS["Mipha, the Zora Princess"][0]
        self.assertEqual([prepared[o + record] for o, _ in starter_save.STATE_LISTS], [2, 2])
        hf = L.MISSION_RECORD_IDS["The Battle of Hyrule Field"][0]
        self.assertEqual([prepared[o + hf] for o, _ in starter_save.STATE_LISTS], [3, 3])  # stays cleared

    def test_switch_plan(self) -> None:
        from ..client.starter_save import plan_switch
        self.assertEqual(plan_switch("B", "B", False, False, True)[0], "none")
        self.assertEqual(plan_switch("B", None, True, False, True)[:2], ("starter", False))  # fresh save, new seed
        self.assertEqual(plan_switch("B", None, False, False, True)[0], "refuse")  # unknown progress: never automatic
        self.assertEqual(plan_switch("B", None, False, False, True, force=True)[:2], ("starter", True))
        self.assertEqual(plan_switch("A", None, False, False, False)[0], "claim")  # an old seed adopts its save
        self.assertEqual(plan_switch("B", "A", False, False, True)[:2], ("starter", True))  # A's save is parked
        self.assertEqual(plan_switch("A", "B", False, True, True)[:2], ("restore", True))  # back to A: restored
        self.assertEqual(plan_switch("C", "A", False, False, False)[0], "refuse")  # old seed, nothing to switch to

    def test_shelf_round_trip(self) -> None:
        import tempfile
        from pathlib import Path
        from ..client import starter_save
        with tempfile.TemporaryDirectory() as folder:
            shelf = starter_save.SaveShelf(Path(folder) / "saves")
            path = str(Path(folder) / "0" / "svdt")
            self.assertIsNone(shelf.owner(path))
            shelf.set_owner(path, "seedA_Me")
            self.assertEqual(shelf.owner(path), "seedA_Me")
            data = starter_save.template()
            shelf.park("seedA_Me", data)
            self.assertTrue(shelf.has_parked("seedA_Me"))
            self.assertEqual(shelf.take("seedA_Me"), data)
            shelf.park("seedA_Me", data)  # parking again keeps the earlier copy as a dated backup
            self.assertEqual(len(list((Path(folder) / "saves").glob("seedA_Me*.svdt"))), 2)
            target = Path(folder) / "0"
            target.mkdir()
            Path(path).write_bytes(b"old")
            starter_save.install(path, [path], data, Path(folder) / "backups")
            self.assertEqual(Path(path).read_bytes(), data)
            self.assertEqual(len(list((Path(folder) / "backups").iterdir())), 1)


class ProgressiveQuestNameTests(WorldTestBase):
    """A progressive quest reward copy names the quest(s) it unlocks, in the game's own (vanilla) order."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_content": ["Quests"]}

    def test_copies_unlock_in_vanilla_order(self) -> None:
        from ..data_rewards import ALL_GROUPS
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        item = "Progressive Recipe"
        self.assertEqual(session.unlocked_by(item), [])
        session.apply_received_item_names([item])
        first = session.unlocked_by(item)
        self.assertTrue(first)
        self.assertEqual(first[0], ALL_GROUPS[item].known[0])
        self.assertEqual(ALL_GROUPS[item].known[0], "A Feast of Greens")  # opens right after Hyrule Field in vanilla


class MapSelectionTests(WorldTestBase):
    """The world-map cursor (id, kind) maps to the mission, challenge or quest and its checks."""
    game = "Hyrule Warriors Age of Calamity"
    options = {"side_content": ["Challenges", "Quests"], "side_check_density": 100}

    def test_selection_names_and_ids(self) -> None:
        from ..data_save import MISSION_RECORD_IDS, QUEST_STATE_IDS
        session = Session(json.loads(json.dumps(self.world.fill_slot_data())))
        name, ids = session.selection_checks(MISSION_RECORD_IDS["Mipha, the Zora Princess"][0], 2)
        self.assertEqual(name, "Mipha, the Zora Princess")
        self.assertIn(session.mission_ids[name], ids)
        quest = next(q for q in session.ids["quest"] if q in QUEST_STATE_IDS)
        self.assertEqual(session.selection_checks(QUEST_STATE_IDS[quest], 4), (quest, [session.ids["quest"][quest]]))
        self.assertIsNone(session.selection_checks(1, 9))
