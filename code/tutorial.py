import math
import os
import pygame

# ---------- Look ----------
GOLD = (255, 215, 0)
WHITE = (255, 255, 255)
DIM = (150, 150, 165)
INK = (10, 8, 16)
CAPTION_FILL = (12, 12, 20)
CAPTION_ALPHA = 200
CAPTION_W = 560
CAPTION_TOP = 104               # below the order bar at the top of the screen
CAPTION_PAD = 12
FADE_IN_MS = 220
INFO_CLICK_DELAY = 350          # stops a double-click from skipping a caption unread
MIN_STEP_MS = 400

FONT_PATH = "assets/font/monogram.ttf"
_fonts = {}


def _font(size):
    if size not in _fonts:
        _fonts[size] = (pygame.font.Font(FONT_PATH, size) if os.path.exists(FONT_PATH)
                        else pygame.font.Font(None, size))
    return _fonts[size]


def _fn():
    import function          # already loaded by the game; imported lazily so this file stays light
    return function


# ---------- Has the player been through it? ----------
# True once finished or skipped. Losing keeps it False, so the retry plays the walkthrough again.
_state = {"done": False}


def shouldRun(stage):
    return bool(stage.get("tutorial")) and not _state["done"]


def create(stage):
    return Tutorial() if shouldRun(stage) else None


def resetProgress():
    _state["done"] = False


# ---------- Helpers over battle state ----------
def _unit(context, name):
    return next((sprite for sprite in context["sprites"] if sprite["side"] == "left" and sprite["name"] == name and not sprite["dead"]), None)


def _enemy(ctx):
    return next((sprite for sprite in ctx["sprites"] if sprite["side"] == "right" and not sprite["dead"]), None)


def _isGuard(skillDef):
    return skillDef is not None and skillDef.icon in ("dodge", "block")


def _shown(unit, skill):
    """Index of `skill` on the unit's two visible cards, or None if it's on the hidden pair."""
    return unit["buttonSkills"].index(skill) if skill in unit["buttonSkills"] else None


def _inSlots(unit, skill):
    return any(skill in slot for slot in unit["buttonSlots"])


def _allActed(context):
    living = [sprite for sprite in context["sprites"] if sprite["side"] == "left" and not sprite["dead"]]
    return bool(living) and all(sprite["acted"] for sprite in living)


def _queued(context, unit, skill=None):
    return any(action["sprite"] is unit and (skill is None or action["skillName"] == skill) for action in context["queue"])


# ---------- The script ----------
# kind: info   read it, click / SPACE to continue
#       select click `who`                        flip    right-click empty space to flip the cards
#       card   click `skill` on `who`'s cards     target  click an enemy to aim the chosen skill
#       kana   press ENTER / the KANA prompt      free    any input, until `who` has an order
#       watch  a caption while the round plays   (ends when round >= untilRound)
# group: if one step of a group can't happen, the whole group is skipped.
# gate:  the step stays hidden (and input stays free) until this is true.
def _sanityNote(context):
    otab = _unit(context, "Otab")
    if otab is not None and otab["sanity"] < 0.5:
        return ("Look at Otab's sanity bar: Apir cost him some and it's under 50%. Costly skills are locked "
                "for him now (those cards turn red). Guarding and landing heads on coin flips win it back.")
    return ("Sanity decides what you can cast: below 50%, costly skills lock (their cards turn red). "
            "Guarding and landing heads on coin flips win it back.")


STEPS = [
    {"id": "welcome", "kind": "info",
     "text": "Welcome to Kanto Kombat. Each round you give every fighter one order, then everyone acts in "
             "speed order. Let's walk through your first round."},

    # ----- Sandugo: read the cards, flip them, dodge -----
    {"id": "selSandugo", "kind": "select", "who": "Sandugo", "group": "sandugo1",
     "text": "Click Sandugo to give him an order."},
    {"id": "cards", "kind": "info", "group": "sandugo1",
     "text": "Each card shows SPD (lower acts first), DMG (damage or healing), SAN (sanity cost or gain) "
             "and EFF (status effect). Hover a card to read it."},
    {"id": "flip", "kind": "flip", "who": "Sandugo", "group": "sandugo1",
     "text": "Every fighter has four skills, shown two at a time. Right-click empty space to flip the cards."},
    {"id": "ilag", "kind": "card", "who": "Sandugo", "skill": "ilag", "group": "sandugo1",
     "text": "ILAG is a dodge. It's fast (SPD 1) and avoids the next hit completely, "
             "and it restores some sanity. Click it."},

    # ----- Darit: a plain attack -----
    {"id": "selDarit", "kind": "select", "who": "Darit", "group": "darit1", "text": "Now click Darit."},
    {"id": "bato", "kind": "card", "who": "Darit", "skill": "bato", "group": "darit1",
     "text": "BATO is a straight attack. Click it."},
    {"id": "batoTarget", "kind": "target", "who": "Darit", "group": "darit1",
     "text": "Now click an enemy to aim it. Red outlines show who you can hit."},

    # ----- Otab: a debuff -----
    {"id": "selOtab", "kind": "select", "who": "Otab", "group": "otab1", "text": "Now click Otab."},
    {"id": "apir", "kind": "card", "who": "Otab", "skill": "apir", "group": "otab1",
     "text": "APIR hits and lowers the enemy's defense for 2 rounds, but it costs sanity. Click it."},
    {"id": "apirTarget", "kind": "target", "who": "Otab", "group": "otab1",
     "text": "Aim it at the same enemy: lowered defense makes every later hit hurt more."},

    # ----- the round -----
    {"id": "orderbar", "kind": "info",
     "text": "The bar at the top is the turn order and the arrows show who targets whom. Lower SPD goes "
             "first: guards, then normal attacks, then ultimates last."},
    {"id": "sanity", "kind": "info",
     "text": "The bar under each fighter is SANITY. Everyone starts at 50%. Higher means more damage and "
             "luckier coin flips; lower means less damage and worse luck."},
    {"id": "kana", "kind": "kana",
     "text": "Everyone has an order. Press ENTER or click KANA to start the round."},
    {"id": "coins", "kind": "watch", "untilRound": 2,
     "text": "Every action flips two coins: 0 heads is 75% damage, 1 is 100%, 2 is 125%, and heads restore "
             "a little sanity. Equal-speed fighters aiming at each other CLASH: more heads goes first. "
             "The Battle Log (bottom-left) records it all."},

    # ----- round 2 -----
    {"id": "status", "kind": "info", "gate": lambda c: c["round"] >= 2,
     "text": "Round 2. Small icons beside a fighter show active effects and the turns left. Buffs and "
             "debuffs change attack or defense, and other skills cause bleed, poison or stun."},
    {"id": "sanity2", "kind": "info", "text": _sanityNote},

    {"id": "selDarit2", "kind": "select", "who": "Darit", "group": "darit2", "text": "Click Darit again."},
    {"id": "bukol", "kind": "card", "who": "Darit", "skill": "bukol", "group": "darit2",
     "text": "BUKOL is an area skill: it hits your target in full and the other enemies for half. Click it."},
    {"id": "bukolTarget", "kind": "target", "who": "Darit", "group": "darit2",
     "text": "Click any enemy. All of them will be hit."},

    {"id": "selSandugo2", "kind": "select", "who": "Sandugo", "group": "sandugo2", "text": "Now Sandugo."},
    {"id": "pinaikot", "kind": "card", "who": "Sandugo", "skill": "pinaikot", "group": "sandugo2",
     "text": "PINAIKOT is an ultimate: huge damage, but slowest (SPD 4), 30% sanity, and it boosts his own "
             "attack for 3 rounds. Click it."},
    {"id": "pinaikotTarget", "kind": "target", "who": "Sandugo", "group": "sandugo2",
     "text": "Click an enemy to aim it."},

    {"id": "freeOtab", "kind": "free", "who": "Otab",
     "text": "Your call, Otab. Pick any skill you like (right-click flips his cards)."},
    {"id": "kana2", "kind": "kana", "text": "Send it. Press ENTER or click KANA."},

    {"id": "outro", "kind": "info", "gate": lambda c: c["round"] >= 3,
     "text": "That's the core of it. Keep going until the enemy team is down. [S] changes battle speed "
             "and ESC pauses."},
]


# ---------- Text drawing ----------
def _wrap(text, font, maxWidth):
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            trial = word if not line else f"{line} {word}"
            if font.size(trial)[0] <= maxWidth:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
    return lines


def _ring(window, rect, grow=6):
    pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.008)
    glowGrowth = 8 + int(grow * pulse)
    pygame.draw.rect(window, GOLD, rect.inflate(glowGrowth, glowGrowth), 3, border_radius=10)


_INK_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))
ARROW_FONT_SIZE = 56            # same monogram ">" as the speed control, bigger so it reads over the battle
ARROW_INK = 2                   # outline thickness, same as the speed control's hover state
_arrowCache = {}


def _arrowSurface():
    """The speed control's ">" (monogram font, gold, dark outline + drop shadow), turned to point down."""
    surf = _arrowCache.get("v")
    if surf is None:
        font = _font(ARROW_FONT_SIZE)
        front = font.render(">", True, GOLD)
        dark = font.render(">", True, INK)
        outlineSize = ARROW_INK
        pad = outlineSize * 2
        glyph = pygame.Surface((front.get_width() + pad * 2, front.get_height() + pad * 2), pygame.SRCALPHA)
        glyph.blit(dark, (pad + outlineSize, pad + outlineSize * 2))                       # drop shadow
        for dx, dy in _INK_OFFSETS:
            glyph.blit(dark, (pad + dx * outlineSize, pad + dy * outlineSize))             # outline
        glyph.blit(front, (pad, pad))
        glyph = glyph.subsurface(glyph.get_bounding_rect()).copy()     # trim the empty font padding
        surf = pygame.transform.rotate(glyph, -90)                     # ">" -> points down
        _arrowCache["v"] = surf
    return surf


def _arrow(window, tipX, tipY):
    """A bobbing gold ">" (rotated to point down) in the speed control's style; its point is at (tipX, tipY)."""
    bob = int(6 * math.sin(pygame.time.get_ticks() * 0.008))
    y = tipY - 4 - max(0, bob)
    surf = _arrowSurface()
    window.blit(surf, surf.get_rect(midbottom=(tipX, y + ARROW_INK * 2)))


# ---------- The tutorial ----------
class Tutorial:
    def __init__(self):
        self.index = 0
        self.active = True
        self.flags = set()
        self.ctx = None
        self.stepStart = pygame.time.get_ticks()
        self._cache = {}

    # ----- progress -----
    def current(self):
        return STEPS[self.index] if self.active and self.index < len(STEPS) else None

    def notify(self, name):
        self.flags.add(name)

    def _go(self, index):
        self.index = index
        self.flags.clear()
        self.stepStart = pygame.time.get_ticks()
        if self.index >= len(STEPS):
            self.finish(True)

    def _advance(self):
        self._go(self.index + 1)

    def _skipGroup(self):
        group = STEPS[self.index].get("group")
        i = self.index + 1
        while group is not None and i < len(STEPS) and STEPS[i].get("group") == group:
            i += 1
        self._go(i)

    def finish(self, completed):
        self.active = False
        if completed:
            _state["done"] = True

    # ----- can this step still happen? -----
    def _impossible(self, step, context):
        who = step.get("who")
        unit = _unit(context, who) if who else None
        if who and unit is None:
            return True
        kind = step["kind"]
        if kind == "card":
            skill = step["skill"]
            if not _inSlots(unit, skill):
                return True
            skillDef = _fn().getSkillDef(unit["name"], skill)
            if skillDef is None or _fn().skillLockedBySanity(unit, skillDef):
                return True
        if kind == "target" and _enemy(context) is None:
            return True
        return False

    def _open(self, step):
        gate = step.get("gate")
        return gate is None or self.ctx is None or gate(self.ctx)

    def _done(self, step, context):
        kind = step["kind"]
        unit = _unit(context, step["who"]) if step.get("who") else None
        if kind == "select":
            return context["selected"] is unit
        if kind == "flip":
            return "cycle" in self.flags
        if kind == "card":
            skillDef = _fn().getSkillDef(unit["name"], step["skill"])
            if _isGuard(skillDef):
                return _queued(context, unit, step["skill"])
            return (context["selected"] is unit and context["pending"] is not None
                    and unit["buttonSkills"][context["pending"]] == step["skill"]) or _queued(context, unit, step["skill"])
        if kind == "target":
            return _queued(context, unit)
        if kind == "free":
            return _queued(context, unit)
        if kind == "kana":
            return context["busy"]
        if kind == "watch":
            return context["round"] >= step["untilRound"]
        return False        # info: only the player's click moves it on

    def update(self, context, dt):
        """ctx: sprites, selected, pending, queue, busy, round, result, endTurnRect, view."""
        self.ctx = context
        if not self.active:
            return
        if context["result"] is not None:
            self.finish(context["result"] == "victory")      # lose -> the retry replays it
            return
        step = self.current()
        if step is None:
            return
        if not self._open(step):
            return
        if step["kind"] != "info" and self._impossible(step, context):
            self._skipGroup()
            return
        if pygame.time.get_ticks() - self.stepStart >= MIN_STEP_MS and self._done(step, context):
            self._advance()

    # ----- input: the heart of "forced" -----
    def handleEvent(self, event, scenePos=None):
        """True = swallow this event; the battle never sees it."""
        if not self.active or self.ctx is None:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_t:
            self.finish(True)
            return True
        step = self.current()
        context = self.ctx
        if step is None or context["result"] is not None or not self._open(step):
            return False
        # While a round plays out the battle ignores input anyway; let ESC / S / wheel / clicks through.
        if context["busy"]:
            return False
        kind = step["kind"]
        if kind == "kana" and not _allActed(context):
            kind = "free"                      # KANA isn't on screen yet: never trap the player

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_s):
                return False
            if kind == "info" and event.key == pygame.K_SPACE:
                self._infoNext()
                return True
            if event.key == pygame.K_RETURN:
                return kind not in ("kana", "free")
            return kind != "free"
        if event.type != pygame.MOUSEBUTTONDOWN:
            return False                                  # motion / wheel / releases pass through
        if kind == "free":
            return False
        if kind == "watch":
            return False
        if kind == "info":
            if event.button == 1:
                self._infoNext()
            return True
        return not self._mouseAllowed(step, event, scenePos)

    def _infoNext(self):
        if pygame.time.get_ticks() - self.stepStart >= INFO_CLICK_DELAY:
            self._advance()

    def _mouseAllowed(self, step, event, scenePos):
        functionsModule, context, kind = _fn(), self.ctx, step["kind"]
        unit = _unit(context, step["who"]) if step.get("who") else None
        selected, pending, sprites = context["selected"], context["pending"], context["sprites"]

        if kind == "kana":
            rect = context.get("endTurnRect")
            return event.button == 1 and rect is not None and rect.collidepoint(event.pos)
        if scenePos is None:
            return False
        if kind == "select":
            return (event.button == 1 and selected is None and unit is not None
                    and functionsModule.getSelectableSprite(sprites, scenePos) is unit)
        if kind == "flip":
            return (event.button == 3 and selected is unit and pending is None
                    and functionsModule.getClickedButton(selected, scenePos) is None)
        if kind == "card":
            if selected is not unit or pending is not None:
                return False
            if _shown(unit, step["skill"]) is None:       # the card is on the other pair: allow the flip
                return event.button == 3 and functionsModule.getClickedButton(selected, scenePos) is None
            return (event.button == 1
                    and functionsModule.getClickedButton(selected, scenePos) == _shown(unit, step["skill"]))
        if kind == "target":
            return (event.button == 1 and selected is unit and pending is not None
                    and functionsModule.getEnemyTarget(sprites, selected, scenePos) is not None)
        return False

    # ----- what to point at -----
    def focusTargets(self, sprites):
        """[(sprite, color, strength)] to glow: the fighter to click, or the enemy to aim at."""
        step = self.current()
        if step is None or self.ctx is None or not self._open(step):
            return []
        pulse = 0.45 + 0.3 * math.sin(pygame.time.get_ticks() * 0.006)
        if step["kind"] == "select":
            unit = _unit(self.ctx, step["who"])
            return [(unit, WHITE, pulse)] if unit is not None else []
        if step["kind"] == "target":
            enemy = _enemy(self.ctx)
            return [(enemy, (255, 90, 90), pulse)] if enemy is not None else []
        return []

    def _pointers(self, step, window):
        """Draws the pointer / ring for the current step (screen space)."""
        context, functionsModule, kind = self.ctx, _fn(), step["kind"]
        zoom, focus, pan = context["view"]
        toScreen = lambda unitRect: functionsModule.sceneRectToScreen(unitRect, zoom, focus, pan)
        unit = _unit(context, step["who"]) if step.get("who") else None

        if kind == "select" and unit is not None:
            unitRect = toScreen(unit["stats"].rect)
            _arrow(window, unitRect.centerx, unitRect.top - 24)
        elif kind == "target":
            enemy = _enemy(context)
            if enemy is not None:
                unitRect = toScreen(enemy["stats"].rect)
                _arrow(window, unitRect.centerx, unitRect.top - 24)
        elif kind in ("card", "flip") and unit is not None and context["selected"] is unit:
            cards = [toScreen(unitRect) for unitRect in functionsModule.getButtonRect(unit)]
            idx = _shown(unit, step["skill"]) if kind == "card" else None
            if kind == "card" and idx is not None and context["pending"] is None:
                _ring(window, cards[idx])
                _arrow(window, cards[idx].centerx, cards[idx].top - 26)
            elif cards:                                     # flip (or the wanted card is on the other pair)
                top = min(card.top for card in cards)
                midX = (cards[0].left + cards[-1].right) // 2
                _arrow(window, midX, top - 34)
        elif kind == "kana":
            rect = context.get("endTurnRect")
            if rect is not None:
                _ring(window, rect.inflate(10, 6))

    def _caption(self, step):
        text = step["text"](self.ctx) if callable(step["text"]) else step["text"]
        key = (step["id"], text)
        if key not in self._cache:
            self._cache.clear()
            self._cache[key] = _wrap(text, _font(22), CAPTION_W - 2 * CAPTION_PAD - 6)
        return self._cache[key]

    def draw(self, window):
        step = self.current()
        if step is None or self.ctx is None or not self._open(step) or self.ctx["result"] is not None:
            return
        busy = self.ctx["busy"]
        if not busy:
            self._pointers(step, window)
        elif step["kind"] != "watch":
            return                                          # keep the screen clean mid-round

        font = _font(22)
        lineH = font.get_linesize()
        lines = self._caption(step)
        hint = "click to continue" if step["kind"] == "info" else ""
        height = CAPTION_PAD * 2 + len(lines) * lineH + 16
        box = pygame.Surface((CAPTION_W, height), pygame.SRCALPHA)
        pygame.draw.rect(box, (*CAPTION_FILL, CAPTION_ALPHA), box.get_rect(), border_radius=10)
        pygame.draw.rect(box, GOLD, (0, 10, 4, height - 20), border_radius=2)       # thin accent bar
        y = CAPTION_PAD
        for line in lines:
            box.blit(font.render(line, True, WHITE), (CAPTION_PAD + 6, y))
            y += lineH
        small = _font(16)
        tag = small.render("T  skip", True, DIM)
        box.blit(tag, (CAPTION_W - tag.get_width() - 10, height - tag.get_height() - 4))
        if hint:
            hintSurface = small.render(hint, True, GOLD)
            box.blit(hintSurface, (CAPTION_PAD + 6, height - hintSurface.get_height() - 4))

        age = pygame.time.get_ticks() - self.stepStart
        box.set_alpha(int(255 * min(1.0, age / FADE_IN_MS)))
        window.blit(box, box.get_rect(midtop=(window.get_width() // 2, CAPTION_TOP)))


# ---------- Team-select tip ----------
def teamSelectTip(window):
    windowWidth, windowHeight = window.get_size()
    font = _font(20)
    text = ("Your team is ready: Sandugo, Darit and Otab. Hover a skill icon to read it, then click Palag.")
    label = font.render(text, True, WHITE)
    box = label.get_rect().inflate(28, 14)
    box.midbottom = (windowWidth // 2, windowHeight - 6)
    surf = pygame.Surface(box.size, pygame.SRCALPHA)
    pygame.draw.rect(surf, (*CAPTION_FILL, 190), surf.get_rect(), border_radius=10)
    pygame.draw.rect(surf, GOLD, (0, 8, 4, box.height - 16), border_radius=2)
    surf.blit(label, (14, 7))
    window.blit(surf, box.topleft)