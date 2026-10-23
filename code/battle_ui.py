import os
import sys
import pygame
from entities import CHARACTER, IDLE_ANIMATIONS_CONFIG, SKILL_ANIMATIONS_CONFIG
from function import *
from animation import (
    CoinFlipAnim, drawCoinFlip, loadCoinFrames, updateDamagePopups, drawDamagePopups,
    updateComboDisplays, drawComboDisplays, comboBadgeWidth, COMBO_SIDE_GAP,
    loadIdleAnimations, updateIdleAnimations,
    loadSkillEffect, loadSplashEffect, splashDelayFor, splashStartsWithPrimary, drawSkillEffect, REPLACE_IDLE,
    updateStatusArrowPopups, drawStatusArrowPopups, STATUS_ARROW_DURATION,
    updateDeathAnimations, drawDeadSprite, drawDeathFliers, BossFX,
)
# applyActionDamage.
from character_select_ui import runCharacterSelect, CHARACTER_SELECT_BACK
from stages import getStage, buildBattleLayout, DEFAULT_BACKGROUND
from pause_menu import runPauseMenu, runConfirm, runSlotMenu, drawHudIcons, showToast
import saves
import settings
import tutorial
from voice import playSkillVoice, updateVoiceDucking, voicesPlaying

# Set when the menu music is faded out for a fight, so campaign.py knows to bring it back.
battleMusicState = {"menuFaded": False}

# ---------- Battle entry point ----------

_battleSpeed = [settings.preferences["battle_speed"]]      # remembered between launches


def _stepBattleSpeed():
    """> -> >> -> >>> and remember the choice."""
    _battleSpeed[0] = nextBattleSpeed(_battleSpeed[0])
    settings.preferences["battle_speed"] = _battleSpeed[0]
    settings.saveSettings()

RESULT_CONTINUE_DELAY = RESULT_SHOW_DELAY + RESULT_HINT_DELAY      # when a click is accepted (timeline lives in function.py)

_sharedAssets = {}


def _getSharedAssets():
    if not _sharedAssets:
        _sharedAssets["coins"] = loadCoinFrames()
        _sharedAssets["skillIcons"] = loadSkillIcons()
        _sharedAssets["statusIcons"] = loadStatusIcons()
    return _sharedAssets["coins"], _sharedAssets["skillIcons"], _sharedAssets["statusIcons"]


def _loadStageBackground(stage, width, height):
    """The stage's battlefield, scaled to the padded size both character select and the battle's bigSceneSurface need."""
    path = stage.get("background") or DEFAULT_BACKGROUND
    if not os.path.exists(path):
        print(f"[battle] background missing: {path} -> using {DEFAULT_BACKGROUND}")
        path = DEFAULT_BACKGROUND
    img = pygame.image.load(path).convert()
    return pygame.transform.scale(img, (width + 2 * CAMERA_PAN_MARGIN, height + 2 * CAMERA_PAN_MARGIN))


# ---------- Battle gradient ----------
BATTLE_DIM_ALPHA = 35            # flat darkening over the whole image
BATTLE_BOTTOM_START = 0.40
BATTLE_BOTTOM_ALPHA = 165        # darkness at the very bottom edge
BATTLE_TOP_END = 0.22
BATTLE_TOP_ALPHA = 90            # darkness at the very top edge
BATTLE_GRADIENT_COLOR = (6, 6, 12)


def _withBattleGradient(background):
    """Returns a copy of the (padded) battlefield with the gradient baked in."""
    backgroundWidth, backgroundHeight = background.get_size()
    overlay = pygame.Surface((backgroundWidth, backgroundHeight), pygame.SRCALPHA)
    overlay.fill((*BATTLE_GRADIENT_COLOR, BATTLE_DIM_ALPHA))
    bottomStart = int(backgroundHeight * BATTLE_BOTTOM_START)
    topEnd = int(backgroundHeight * BATTLE_TOP_END)
    for y in range(backgroundHeight):
        extra = 0
        if y >= bottomStart:
            gradientProgress = (y - bottomStart) / max(1, backgroundHeight - bottomStart)
            extra += BATTLE_BOTTOM_ALPHA * (gradientProgress ** 1.3)
        if y < topEnd:
            gradientProgress = 1 - y / max(1, topEnd)
            extra += BATTLE_TOP_ALPHA * (gradientProgress ** 1.5)
        if extra:
            pygame.draw.line(overlay, (*BATTLE_GRADIENT_COLOR, min(255, BATTLE_DIM_ALPHA + int(extra))), (0, y), (backgroundWidth, y))
    out = background.copy()
    out.blit(overlay, (0, 0))
    return out.convert()


def runBattle(window, chapterName, stageIndex, onSave=None, onLoad=None):
    """onSave(slot) -> bool writes that slot; onLoad(slot) -> bool reloads it (both optional, wired by campaign/start)."""
    stage = getStage(chapterName, stageIndex)
    screen_width, screen_height = window.get_size()

    # ---------- Camera ----------
    CAMERA = CameraRig((screen_width, screen_height))
    bigSceneSurface = CAMERA.bigSurface
    sceneSurface = CAMERA.sceneSurface

    clock = CAMERA.clock
    FPS = 60

    # ---------- Assets (this stage's background, coins, icons) ----------
    background_img = _loadStageBackground(stage, screen_width, screen_height)
    COIN_FRAMES, SKILL_ICONS, STATUS_ICONS = _getSharedAssets()

    # ---------- Character select ----------
    isBoss = stage.get("kind") == "boss"
    stageLabel = f"{chapterName} - {stage.get('title', f'Stage {stageIndex + 1}')}"
    selectedTeam = runCharacterSelect(
        window, screen_width, screen_height, SKILL_ICONS, CAMERA, background_img,
        subtitle=stageLabel,
        subtitleColor=(255, 90, 90) if isBoss else (255, 215, 0),   # boss fights get a red label
        overlay=tutorial.teamSelectTip if tutorial.shouldRun(stage) else None,
        defaultTeam=stage.get("tutorialTeam") if tutorial.shouldRun(stage) else None,
        lockTeam=tutorial.shouldRun(stage),
    )
    if selectedTeam is None:
        return "quit"
    if selectedTeam == CHARACTER_SELECT_BACK:
        return "back"

    # No track of its own: fade the menu music out instead of carrying it into the fight.
    if not stage.get("music") and pygame.mixer.get_init() and pygame.mixer.music.get_busy():
        pygame.mixer.music.fadeout(800)
        battleMusicState["menuFaded"] = True

    # ---------- Select-screen snapshot for the wipe ----------
    selectScreenFrame = CAMERA.bigSurface.copy()

    # From here on the battle uses the gradient-darkened battlefield.
    background_img = _withBattleGradient(background_img)

    # ---------- Battle sprites ----------
    battleLayout = buildBattleLayout(stage, selectedTeam)

    sprites = []
    for entry in battleLayout:
        stats = CHARACTER[entry["name"]]["make"]()
        # Optional per-enemy tweaks from the stage config (see stages.py).
        if entry.get("hpMult"):
            stats.maxHp = max(1, round(stats.maxHp * entry["hpMult"]))
            stats.hp = stats.maxHp
        if entry.get("scale") and entry["scale"] != 1:
            imageWidth, imageHeight = stats.image.get_size()
            stats.image = pygame.transform.smoothscale(
                stats.image, (max(1, round(imageWidth * entry["scale"])), max(1, round(imageHeight * entry["scale"]))))
            stats.rect = stats.image.get_rect()
        stats.rect.center = (entry["x"], entry["y"])
        buttonSlots = CHARACTER[entry["name"]].get("buttonSlots", [])
        sprites.append({
            **entry,
            "stats": stats,
            "selected": False,
            "acted": False,
            "dead": False,
            "sanity": 0.5,
            "guard": None,
            "displayHp": stats.hp,
            "displaySanity": 0.5,
            "buttonSlots": buttonSlots,
            "buttonIndex": [0] * len(buttonSlots),
            "buttonSkills": [slot[0] for slot in buttonSlots],
        })

    # ---------- Idle animations ----------
    idleAnimations = loadIdleAnimations(IDLE_ANIMATIONS_CONFIG, sprites)

    # Builds the faded-copy / glow-stencil caches for every idle frame right now.
    prewarmImageCaches(idleAnimations)

    # ---------- Opening frame and wipe transition ----------
    battleOpeningFrame = pygame.Surface(CAMERA.bigSize).convert()
    battleOpeningFrame.blit(background_img, (0, 0))
    openingScene = battleOpeningFrame.subsurface((CAMERA_PAN_MARGIN, CAMERA_PAN_MARGIN, screen_width, screen_height))
    for currentSprite in sprites:
        drawChar(openingScene, currentSprite, statusIcons=STATUS_ICONS)

    def _playOpeningIdle(dt):
        """wipeTransition's onUpdate hook: advances every sprite's idle animation and redraws them onto openingScene."""
        updateIdleAnimations(sprites, idleAnimations, dt)
        drawBg(battleOpeningFrame, background_img)
        for sprite in sprites:
            drawChar(openingScene, sprite, statusIcons=STATUS_ICONS)

    wipeTransition(window, selectScreenFrame, battleOpeningFrame, (screen_width, screen_height), clock=CAMERA.clock, overlay=drawFps, camera=CAMERA, onUpdate=_playOpeningIdle,
                   banner=makeStageBanner(chapterName, stage.get("title", f"Stage {stageIndex + 1}"), isBoss))

    bossFx = BossFX((screen_width, screen_height)) if isBoss else None     # distortion / glitch / vignette / embers

    # ---------- Battle state (selection, queue, popups) ----------
    selectedSprite = None
    pendingButtonIndex = None

    actionQueue = []
    damagePopups = []
    comboDisplays = []
    statusPopups = []
    battleLog = createBattleLog()

    # ---------- Sort and resolve state ----------
    sortGenerator = None
    sortTimer = 0
    sortActiveIndex = None
    sortStepDelay = 350

    coinAnim = None

    resolveGenerator = None
    resolveTimer = 0
    skillAnim = None
    resolveStepDelay = 500

    # ---------- Status effect timing ----------
    EFFECT_RESOLVE_DELAY = 300

    # An action whose status-effect resolution is queued up on pendingEffectAction.
    pendingEffectAction = None

    statusVisualZoom = None

    # ---------- Guard reactions (dodge / block) ----------
    guardReactionAnims = []

    # A skill effect landing on a sprite that BLOCKED it isn't removed.
    BLOCKED_EFFECT_ALPHA = 70
    BLOCKED_EFFECT_FADE_MS = 150

    def blockedEffectAlpha(anim):
        blockedAt = anim.action.get("_blockedAt", {}).get(id(anim.target))
        if blockedAt is None:
            return 255
        fadeProgress = min(1.0, (pygame.time.get_ticks() - blockedAt) / BLOCKED_EFFECT_FADE_MS)
        return round(255 + (BLOCKED_EFFECT_ALPHA - 255) * fadeProgress)

    def spawnGuardReactions(action, minDuration=0):
        """Starts a dodge/block reaction for every guard stance consumed by `action`."""
        for target, guardKind in popGuardReactions(action):
            if guardKind == "block":
                # Remember when this sprite blocked this action.
                action.setdefault("_blockedAt", {}).setdefault(id(target), pygame.time.get_ticks())
            # Find the guard skill by ICON, not by name.
            guardSkillDef = next(
                (skillDef for skillDef in CHARACTER[target["name"]]["skills"] if skillDef.icon == guardKind),
                None,
            )
            if guardSkillDef is None:
                continue
            reactionAction = {
                "sprite": target,
                "target": target,
                "skillName": guardSkillDef.name,
                "skillDef": guardSkillDef,
            }
            anim = loadSkillEffect(reactionAction, SKILL_ANIMATIONS_CONFIG)
            if anim is not None:
                if minDuration > anim.duration:
                    extra = minDuration - anim.duration
                    anim.hold_time += extra
                    anim.duration += extra
                    anim.loop = True
                guardReactionAnims.append(anim)

    # ---------- AOE splash effects ----------
    splashEffectAnims = []
    # Splash copies still waiting out their stagger delay (see animation.
    pendingSplashEffects = []

    def spawnSplashEffects(action):
        """Starts the splash effect on every extra AOE target hit by `action`."""
        targets = popSplashEffectTargets(action)   # always pop, so the list is cleared
        if action.get("_splashAnimsStarted"):
            return
        _queueSplashEffects(action, targets)

    def _queueSplashEffects(action, targets):
        """Builds one splash copy per target and starts it now."""
        delay = splashDelayFor(action, SKILL_ANIMATIONS_CONFIG)
        for i, target in enumerate(targets):
            anim = loadSplashEffect(action, target, SKILL_ANIMATIONS_CONFIG)
            if anim is None:
                continue
            if delay > 0 and i > 0:
                pendingSplashEffects.append([delay * i, anim])   # staggered: start later
            else:
                splashEffectAnims.append(anim)                   # starts right now

    def startSplashEffects(action):
        """Called the moment a damage/heal skill's animation STARTS."""
        if not splashStartsWithPrimary(action, SKILL_ANIMATIONS_CONFIG):
            return
        targets = [sprite for sprite, _fraction in getActionTargets(action)[1:] if not sprite["dead"]]
        if not targets:
            return
        action["_splashAnimsStarted"] = True
        _queueSplashEffects(action, targets)

    # ---------- Status effect resolution ----------
    def resolveEffects(action, statusPopups, phase="timed"):
        """Applies `action`'s selfEffect and, for a buff/debuff, its target effect too."""
        skillDef = action["skillDef"]
        instant = phase == "instant"
        # Each slot lands in the phase its OWN duration picks: no duration -> "instant".
        applyActionSelfEffect(action, instant)
        if targetEffectFires(skillDef):
            applyActionEffect(action, instant)
            if skillDef.kind in ("buff", "debuff"):
                spawnSplashEffects(action)
        return spawnEffectVisuals(action, statusPopups)

    # ---------- Round state ----------
    currentTurnAction = None

    roundNumber = 1
    battleResult = None
    logRoundMarker(battleLog, roundNumber)

    # ---------- Camera zoom state ----------
    cameraZoom = CAMERA_ZOOM_IDLE
    cameraFocus = (screen_width // 2, screen_height // 2)
    targetCameraFocus = cameraFocus
    # (the smoothed mouse-follow pan lives on CAMERA.followOffset)

    # ---------- Tutorial overlay (None unless this stage has "tutorial": True) ----------
    tutorialGuide = tutorial.create(stage)

    # ---------- Main loop ----------
    running = True
    resultElapsed = 0
    speedRects = []
    iconRects = {}
    hudAction = None
    endTurnRect = None
    canEndTurn = False
    while running:
        rawDt = clock.tick(FPS)
        updateVoiceDucking()      # music dips while a skill voice is playing
        # Battle speed: only the sort / resolve phase runs faster.
        turnsPlaying = (sortGenerator is not None or resolveGenerator is not None
                        or coinAnim is not None or skillAnim is not None
                        or pendingEffectAction is not None)
        dt = max(1, round(rawDt * _battleSpeed[0])) if turnsPlaying else rawDt
        if battleResult is not None:
            resultElapsed += rawDt

        # ---------- Camera zoom targets ----------
        if statusVisualZoom is not None:
            statusVisualZoom["elapsed"] += dt
            if statusVisualZoom["elapsed"] >= STATUS_ARROW_DURATION:
                statusVisualZoom = None

        zoomingIn = selectedSprite is not None and pendingButtonIndex is None
        if zoomingIn:
            cameraTargetZoom = CAMERA_ZOOM_SKILL_SELECT
            targetCameraFocus = selectedSprite["stats"].rect.center
        elif coinAnim is not None:
            # zoom in on whoever's coins are currently flipping.
            coinPositions = [queuedAction["sprite"]["stats"].rect.center for queuedAction in coinAnim.actions]
            targetCameraFocus = (
                sum(coinPosition[0] for coinPosition in coinPositions) / len(coinPositions),
                sum(coinPosition[1] for coinPosition in coinPositions) / len(coinPositions),
            )
            cameraTargetZoom = CAMERA_ZOOM_SKILL_SELECT if len(coinPositions) == 1 else CAMERA_ZOOM_CLASH
        elif skillAnim is not None:
            targetCameraFocus = skillAnim.cameraFocus
            cameraTargetZoom = CAMERA_ZOOM_SKILL_PLAY

            # If this skill's target currently has a combo readout showing.
            activeCombo = next((combo for combo in comboDisplays if combo["target"] is skillAnim.target), None)
            if activeCombo is not None:
                targetRect = skillAnim.target["stats"].rect
                badgeRight = targetRect.right + COMBO_SIDE_GAP + comboBadgeWidth(activeCombo)
                reach = badgeRight - targetCameraFocus[0]
                if reach > 0:
                    zoomFit = (screen_width / 2 - CAMERA_ZOOM_FIT_MARGIN) / reach
                    cameraTargetZoom = max(CAMERA_ZOOM_SKILL_PLAY_FLOOR, min(cameraTargetZoom, zoomFit))
        elif pendingEffectAction is not None:
            targetCameraFocus = pendingEffectAction["focus"]
            cameraTargetZoom = CAMERA_ZOOM_STATUS_EFFECT
        elif statusVisualZoom is not None:
            # A buff/debuff just landed, right after its skill's own cast animation finished.
            targetCameraFocus = statusVisualZoom["focus"]
            cameraTargetZoom = CAMERA_ZOOM_STATUS_EFFECT
        else:
            cameraTargetZoom = CAMERA_ZOOM_IDLE

        # ---------- Camera update ----------
        cameraZoom = lerpCameraZoom(cameraZoom, cameraTargetZoom, dt)
        cameraFocus = lerpPoint(cameraFocus, targetCameraFocus, dt)

        # let the frame lean a little toward wherever the mouse is pointing.
        CAMERA.update(dt)

        mousePos = CAMERA.toScene(pygame.mouse.get_pos(), cameraZoom, cameraFocus)

        # ---------- Background and per-frame updates ----------
        drawBg(bigSceneSurface, background_img)

        activeSpriteIds = set()
        if currentTurnAction is not None:
            activeSpriteIds |= {id(currentTurnAction["sprite"]), id(currentTurnAction["target"])}
        if coinAnim is not None:
            activeSpriteIds |= {id(queuedAction["sprite"]) for queuedAction in coinAnim.actions}   # never fade a sprite mid coin-flip
        sortingSprite = None
        if sortActiveIndex is not None and 0 <= sortActiveIndex < len(actionQueue):
            sortingSprite = actionQueue[sortActiveIndex]["sprite"]
            activeSpriteIds.add(id(sortingSprite))

        updateIdleAnimations(sprites, idleAnimations, dt)
        updateHitFlashes(sprites, dt)
        updateDeathAnimations(sprites, dt)
        updateHealFlashes(sprites, dt)
        updateDotFlashes(sprites, dt)
        updateStatBars(sprites, dt)

        # ---------- Guard and splash animation aging ----------
        for _anim in guardReactionAnims[:]:
            _anim.update(dt)
            if _anim.finished:
                guardReactionAnims.remove(_anim)
            else:
                activeSpriteIds.add(id(_anim.attacker))
        for _pending in pendingSplashEffects[:]:
            _pending[0] -= dt
            if _pending[0] <= 0:
                pendingSplashEffects.remove(_pending)
                splashEffectAnims.append(_pending[1])
        for _anim in splashEffectAnims[:]:
            _anim.update(dt)
            if _anim.finished:
                splashEffectAnims.remove(_anim)
            else:
                activeSpriteIds.add(id(_anim.target))

        # ---------- Hidden idle frames (replace-idle skills) ----------
        hiddenIdleIds = set()
        if skillAnim is not None and skillAnim.category == REPLACE_IDLE:
            hiddenIdleIds.add(id(skillAnim.attacker))
        for _anim in guardReactionAnims:
            if _anim.category == REPLACE_IDLE:
                hiddenIdleIds.add(id(_anim.attacker))
        for _anim in splashEffectAnims:
            if _anim.category == REPLACE_IDLE:
                hiddenIdleIds.add(id(_anim.target))

        # ---------- Draw sprites ----------
        for currentSprite in sprites:
            if currentSprite["dead"]:
                drawDeadSprite(sceneSurface, currentSprite)      # butterflies (players) / gamo-gamo (enemies)
                continue
            drawChar(sceneSurface, currentSprite, active=id(currentSprite) in activeSpriteIds, hide_image=(id(currentSprite) in hiddenIdleIds), statusIcons=STATUS_ICONS)
        drawDeathFliers(sceneSurface, sprites)

        if tutorialGuide is not None:
            for _s, _glowColor, _glowStrength in tutorialGuide.focusTargets(sprites):
                drawCharacterGlow(sceneSurface, _s, _glowColor, _glowStrength)

        if actionQueue:
            # Whose arrow is lit: - a clash's actions while their coins flip.
            arrowFocus = None
            skillInProgress = skillAnim is not None or pendingEffectAction is not None
            if coinAnim is not None:
                arrowFocus = list(coinAnim.actions)
            elif resolveGenerator is not None and not skillInProgress:
                arrowFocus = actionQueue[0]
            elif sortActiveIndex is not None and 0 <= sortActiveIndex < len(actionQueue):
                arrowFocus = actionQueue[sortActiveIndex]
            # Anything still waiting its turn is dimmed; only the lit one is bright.
            arrowsWaiting = (sortGenerator is not None or resolveGenerator is not None
                             or coinAnim is not None)
            drawActionArrows(sceneSurface, actionQueue, activeAction=arrowFocus, dimAll=arrowsWaiting)

        # ---------- Vignettes ----------
        vignetteArea = CAMERA.visibleRect(cameraZoom, cameraFocus)
        vignetteSurf = None
        if selectedSprite is not None:
            focusX, focusY = selectedSprite["stats"].rect.center
            vignetteSurf = cachedVignette(CAMERA.bigSize, [(focusX + CAMERA_PAN_MARGIN, focusY + CAMERA_PAN_MARGIN)])
        elif coinAnim is not None:
            clashPositions = [
                (x + CAMERA_PAN_MARGIN, y + CAMERA_PAN_MARGIN)
                for x, y in (queuedAction["sprite"]["stats"].rect.center for queuedAction in coinAnim.actions)
            ]
            vignetteSurf = cachedVignette(CAMERA.bigSize, clashPositions)
        if vignetteSurf is not None and vignetteArea is not None:
            bigSceneSurface.blit(vignetteSurf, vignetteArea.topleft, vignetteArea)

        if coinAnim is not None:
            drawCoinFlip(sceneSurface, coinAnim, COIN_FRAMES)

        # ---------- Highlights and skill effects ----------
        if currentTurnAction is not None:
            attackerImage = attackerRect = targetImage = targetRect = None
            replaceIdleAnims = [queuedAction for queuedAction in guardReactionAnims if queuedAction.category == REPLACE_IDLE]
            if skillAnim is not None and skillAnim.category == REPLACE_IDLE:
                replaceIdleAnims = replaceIdleAnims + [skillAnim]
            for _repl in replaceIdleAnims:
                anchorSprite = _repl.attacker if _repl.anchor == "self" else _repl.target
                frame = _repl.frame
                if frame is None:
                    continue
                fx, fy = _repl.position
                frameRect = frame.get_rect(center=(round(fx), round(fy)))
                if anchorSprite is currentTurnAction["sprite"]:
                    attackerImage, attackerRect = frame, frameRect
                elif anchorSprite is currentTurnAction["target"]:
                    targetImage, targetRect = frame, frameRect
            drawTurnHighlight(sceneSurface, currentTurnAction,
                               attacker_image=attackerImage, attacker_rect=attackerRect,
                               target_image=targetImage, target_rect=targetRect)

        if sortingSprite is not None:
            drawSortHighlight(sceneSurface, sortingSprite)

        if skillAnim is not None:
            drawSkillEffect(sceneSurface, skillAnim, blockedEffectAlpha(skillAnim))
        for _anim in guardReactionAnims:
            drawSkillEffect(sceneSurface, _anim)
        for _anim in splashEffectAnims:
            drawSkillEffect(sceneSurface, _anim, blockedEffectAlpha(_anim))

        # ---------- Hover outline ----------
        busy = sortGenerator is not None or resolveGenerator is not None or coinAnim is not None
        pendingSkillDef = None
        if selectedSprite is not None and pendingButtonIndex is not None:
            pendingSkillDef = getSkillDef(selectedSprite["name"], selectedSprite["buttonSkills"][pendingButtonIndex])
        hovered = None
        if not busy and battleResult is None:
            hovered = getHoveredSprite(sprites, selectedSprite, pendingButtonIndex, mousePos, pendingSkillDef)
            if hovered is selectedSprite or (hovered is not None and hovered["dead"]):
                hovered = None

        if hovered is not None and pendingButtonIndex is None:
            drawCharacterGlow(sceneSurface, hovered, (255, 255, 255))

        # ---------- Popups (damage / combo / status) ----------
        trackSanityChanges(sprites, damagePopups)   # "+10%" / "-10%" beside the sanity bar
        updateDamagePopups(damagePopups, dt)
        drawDamagePopups(sceneSurface, damagePopups)
        updateComboDisplays(comboDisplays, dt)
        drawComboDisplays(sceneSurface, comboDisplays)
        updateStatusArrowPopups(statusPopups, dt)
        drawStatusArrowPopups(sceneSurface, statusPopups)

        # ---------- Target preview ----------
        if selectedSprite is not None and pendingButtonIndex is not None:
            drawTargetHighlights(sceneSurface, sprites, selectedSprite, pendingSkillDef)
            if hovered is not None:
                # An AOE hits more than just whoever's directly under the cursor.
                for engaged in previewActionTargets(sprites, hovered, pendingSkillDef):
                    drawChar(sceneSurface, engaged, statusIcons=STATUS_ICONS)
                    drawCharacterGlow(sceneSurface, engaged, (255, 255, 255))

        # ---------- Action pipeline: coin flip, sort, resolve ----------
        if coinAnim is not None:
            # sort is paused while a tie's coins are showing / flipping
            coinAnim.update(dt)
            if coinAnim.finished:
                # Sanity's "increase" is deliberately applied here.
                for coinAction in coinAnim.actions:
                    applyActionSanityRegen(coinAction)
                coinAnim = None

        elif sortGenerator is not None:
            sortTimer += dt
            if sortTimer >= sortStepDelay:
                sortTimer = 0
                try:
                    _, sortActiveIndex, flipEvent = next(sortGenerator)
                    if flipEvent is not None:
                        coinAnim = CoinFlipAnim(*flipEvent)
                except StopIteration:
                    sortGenerator = None
                    sortActiveIndex = None
                    for orderNum, queued in enumerate(actionQueue, 1):
                        queued["orderNum"] = orderNum
                    resolveGenerator = resolveActionSteps(actionQueue)
                    resolveTimer = 0
                    currentTurnAction = None

        elif resolveGenerator is not None:
            for deadSprite in markNewDeaths(sprites):
                addBattleLogEntry(battleLog, f"{deadSprite['name']} was defeated!", color=BATTLE_LOG_DEATH_COLOR)
            purgeVoidActions(actionQueue)

            if skillAnim is not None:
                # a skill animation is playing out for the current action.
                skillAnim.update(dt)
                skillKind = getattr(skillAnim.action["skillDef"], "kind", "damage")
                if not isGuardSkill(skillAnim.action["skillDef"]) and skillKind not in ("buff", "debuff"):
                    # A guard skill never deals damage itself.
                    isHeal = isHealSkill(skillAnim.action["skillDef"])
                    for tickIndex in skillAnim.ticksFiredNow:
                        if isHeal:
                            applyActionTickHeal(skillAnim.action, damagePopups, tickIndex, skillAnim.ticks, combos=comboDisplays)
                        else:
                            applyActionTickDamage(skillAnim.action, damagePopups, tickIndex, skillAnim.ticks, combos=comboDisplays)
                        if tickIndex >= skillAnim.ticks - 1:
                            # Flurry's done -- log the ACTUAL total dealt/healed.
                            totalKey = "_shownHeal" if isHeal else "_shownDamage"
                            total = skillAnim.action.get(totalKey, 0)
                            logActionLine(battleLog, skillAnim.action, "heal" if isHeal else "damage", total)
                    if skillAnim.ticksFiredNow:
                        # Whichever of skillAnim's ticks just landed may have been caught by a guard.
                        spawnGuardReactions(skillAnim.action, minDuration=skillAnim.duration - skillAnim.elapsed)
                        # If this was the flurry's last tick.
                        spawnSplashEffects(skillAnim.action)
                if skillAnim.finished:
                    # Any buff/debuff/self-effect has been waiting for exactly this moment.
                    finishedSkillDef = skillAnim.action["skillDef"]
                    if hasTimedEffect(finishedSkillDef):
                        # Don't just reuse skillAnim.cameraFocus here.
                        effectFocusSprite = (
                            skillAnim.action["target"] if hasTimedTargetEffect(finishedSkillDef)
                            else skillAnim.action["sprite"]
                        )
                        pendingEffectAction = {
                            "action": skillAnim.action,
                            "focus": effectFocusSprite["stats"].rect.center,
                            "elapsed": 0,
                            "resolved": False,
                        }
                    skillAnim = None
            elif pendingEffectAction is not None:
                # Still this action's own turn.
                pendingEffectAction["elapsed"] += dt
                if not pendingEffectAction["resolved"]:
                    if pendingEffectAction["elapsed"] >= EFFECT_RESOLVE_DELAY:
                        # The short post-skill beat is up.
                        pendingEffectAction["resolved"] = True
                        visualFired = resolveEffects(pendingEffectAction["action"], statusPopups)
                        if not pendingEffectAction["action"].get("_effectLogged"):
                            logActionLine(battleLog, pendingEffectAction["action"], "effect")
                        if visualFired:
                            statusVisualZoom = {"focus": pendingEffectAction["focus"], "elapsed": 0}
                        else:
                            pendingEffectAction = None
                            resolveTimer = 0
                elif statusVisualZoom is None:
                    # The effect's own visual has now finished playing too -- this action is fully done.
                    pendingEffectAction = None
                    resolveTimer = 0
            else:
                resolveTimer += dt
                # Hold the next action (and the end-of-round) until every voice line has finished (voice.VOICE_CONFIG).
                if resolveTimer >= resolveStepDelay and not voicesPlaying():
                    resolveTimer = 0
                    try:
                        turnAction, flipEvent = next(resolveGenerator)
                        if flipEvent == STUN_SKIP:
                            # Caster is stunned -- the action never goes off (see function.resolveActionSteps).
                            addBattleLogEntry(battleLog, f"{turnAction['sprite']['name']} is stunned and can't act!")
                            currentTurnAction = None
                        elif flipEvent is not None:
                            coinAnim = CoinFlipAnim(*flipEvent)
                            currentTurnAction = None
                        else:
                            currentTurnAction = turnAction
                            playSkillVoice(turnAction)       # random voice for skills, fixed voice for ults (voice.py)
                            # An effect with NO duration lands right now, as the action starts.
                            if hasInstantEffect(turnAction["skillDef"]):
                                resolveEffects(turnAction, statusPopups, "instant")
                                logActionLine(battleLog, turnAction, "effect")
                                turnAction["_effectLogged"] = True
                            # Neither a timed selfEffect nor a buff/debuff's own target effect apply here anymore.
                            if isGuardSkill(turnAction["skillDef"]):
                                # Raising the stance happens right now, as the action starts resolving.
                                activateGuard(turnAction)
                                logActionLine(battleLog, turnAction, "guard")
                                skillAnim = None
                            elif getattr(turnAction["skillDef"], "kind", "damage") in ("buff", "debuff"):
                                # A buff/debuff can still play a configured skill animation for flavor.
                                skillAnim = loadSkillEffect(turnAction, SKILL_ANIMATIONS_CONFIG)
                            else:
                                skillAnim = loadSkillEffect(turnAction, SKILL_ANIMATIONS_CONFIG)
                                if skillAnim is None:
                                    # no animation configured for this skill.
                                    if isHealSkill(turnAction["skillDef"]):
                                        healDealt = applyActionHeal(turnAction, damagePopups)
                                        logActionLine(battleLog, turnAction, "heal", healDealt)
                                    else:
                                        dmgDealt = applyActionDamage(turnAction, damagePopups)
                                        logActionLine(battleLog, turnAction, "damage", dmgDealt)
                                    spawnGuardReactions(turnAction)
                                    spawnSplashEffects(turnAction)
                                else:
                                    startSplashEffects(turnAction)   # copies start together with the primary's
                            if skillAnim is None:
                                # No skill animation is going to play out for this action.
                                if hasTimedEffect(turnAction["skillDef"]):
                                    effectFocusSprite = (
                                        turnAction["target"] if hasTimedTargetEffect(turnAction["skillDef"])
                                        else turnAction["sprite"]
                                    )
                                    pendingEffectAction = {
                                        "action": turnAction,
                                        "focus": effectFocusSprite["stats"].rect.center,
                                        "elapsed": EFFECT_RESOLVE_DELAY,
                                        "resolved": False,
                                    }
                    except StopIteration:
                        resolveGenerator = None
                        currentTurnAction = None
                        deadBefore = {id(currentSprite) for currentSprite in sprites if currentSprite["dead"]}
                        # End-of-round status ticks.
                        checkDead(sprites)
                        if checkBattleResult(sprites) is None:
                            sanityTicks = []
                            for bleeder, dealt, entry in tickStatusEffects(sprites, damagePopups, statusPopups, sanityTicks):
                                addBattleLogEntry(battleLog, f"{bleeder['name']} bleeds for {dealt:.0f}!")
                            for calmer, change, entry in sanityTicks:
                                word = "recovers" if change > 0 else "loses"
                                addBattleLogEntry(battleLog, f"{calmer['name']} {word} {abs(change) * 100:.0f}% sanity!")
                        battleResult, roundNumber = resolveRound(sprites, roundNumber)
                        for currentSprite in sprites:
                            if currentSprite["dead"] and id(currentSprite) not in deadBefore:
                                addBattleLogEntry(battleLog, f"{currentSprite['name']} was defeated!", color=BATTLE_LOG_DEATH_COLOR)
                        if battleResult is None:
                            logRoundMarker(battleLog, roundNumber)

        # ---------- Event handling ----------
        for event in pygame.event.get():
            if tutorialGuide is not None and event.type != pygame.QUIT:
                # The tutorial sees every input first and swallows anything it didn't ask for.
                _tutScenePos = (CAMERA.toScene(event.pos, cameraZoom, cameraFocus)
                                if event.type == pygame.MOUSEBUTTONDOWN else None)
                if tutorialGuide.handleEvent(event, _tutScenePos):
                    continue

            if event.type == pygame.QUIT:
                return "victory_quit" if battleResult == "victory" else "quit"

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and battleResult is None:
                hudAction = "pause"

            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and battleResult is None
                    and any(iconRect.collidepoint(event.pos) for iconRect in iconRects.values())):
                hudAction = next(hudActionName for hudActionName, iconRect in iconRects.items() if iconRect.collidepoint(event.pos))

            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL) and handleBattleLogEvent(
                battleLog, event, roundLocked=(sortGenerator is not None or resolveGenerator is not None or coinAnim is not None)
            ):
                pass

            elif battleResult is not None:
                # Battle's over -- after a short beat.
                if resultElapsed >= RESULT_CONTINUE_DELAY and (
                    event.type == pygame.MOUSEBUTTONDOWN
                    or (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE))
                ):
                    fadeToInk(window, clock)       # result screen -> ink, then the next screen takes over
                    return battleResult
                continue

            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and (
                    any(iconRect.collidepoint(event.pos) for iconRect in speedRects)
                    or (canEndTurn and endTurnRect is not None and endTurnRect.collidepoint(event.pos)))):
                # HUD clicks: the speed selector, or the KANA prompt (same as pressing Enter)
                if any(iconRect.collidepoint(event.pos) for iconRect in speedRects):
                    _stepBattleSpeed()   # the one arrow steps > -> >> -> >>>
                else:
                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r"))

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if sortGenerator is not None or resolveGenerator is not None or coinAnim is not None:
                    continue
                clickPos = CAMERA.toScene(event.pos, cameraZoom, cameraFocus)
                if event.button == 1:
                    if pendingButtonIndex is not None:
                        pendingSkillDef = getSkillDef(selectedSprite["name"], selectedSprite["buttonSkills"][pendingButtonIndex])
                        if isFriendlyTargetSkill(pendingSkillDef):
                            target = getAllyTarget(sprites, selectedSprite, clickPos, pendingSkillDef)
                        else:
                            target = getEnemyTarget(sprites, selectedSprite, clickPos)
                        if target is not None:
                            queueAction(actionQueue, selectedSprite, pendingButtonIndex, target, sprites)
                            selectedSprite = None
                            pendingButtonIndex = None
                        elif getSelectableSprite(sprites, clickPos) is None and getSpriteAt(sprites, clickPos) is None:
                            # clicked empty space while choosing a target: cancel and deselect
                            selectedSprite["selected"] = False
                            selectedSprite = None
                            pendingButtonIndex = None
                    else:
                        buttonIndex = getClickedButton(selectedSprite, clickPos)
                        if buttonIndex is not None:
                            skillName = selectedSprite["buttonSkills"][buttonIndex]
                            skillDef = getSkillDef(selectedSprite["name"], skillName)
                            if skillDef is not None and skillLockedBySanity(selectedSprite, skillDef):
                                pass
                            elif (skillDef is not None and isFriendlyTargetSkill(skillDef)
                                  and not isSelfSkill(skillDef)
                                  and not hasValidAllyTarget(sprites, selectedSprite, skillDef)):
                                pass
                            elif skillDef is not None and isSelfSkill(skillDef):
                                # Dodge/block and self-only skills (self-heal / self-buff) target the caster.
                                queueAction(actionQueue, selectedSprite, buttonIndex, selectedSprite, sprites)
                                selectedSprite = None
                                pendingButtonIndex = None
                            else:
                                pendingButtonIndex = buttonIndex
                        else:
                            selectedSprite = handleClick(clickPos, sprites, selectedSprite)
                            pendingButtonIndex = None
                elif event.button == 3:
                    if pendingButtonIndex is not None:
                        pendingButtonIndex = None
                    elif selectedSprite is not None and getClickedButton(selectedSprite, clickPos) is None:
                        # right-click outside the buttons: switch both skill buttons at once
                        cycleAllButtons(selectedSprite)
                        if tutorialGuide is not None:
                            tutorialGuide.notify("cycle")

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    # Only once every living unit on your team has an action locked in.
                    if (sortGenerator is None and resolveGenerator is None
                            and allPlayersActed(sprites)
                            and any(currentSprite["side"] == "left" and not currentSprite["dead"] for currentSprite in sprites)):
                        if selectedSprite is not None:
                            selectedSprite["selected"] = False
                        selectedSprite = None
                        pendingButtonIndex = None
                        enemyAI(sprites, actionQueue)
                        if actionQueue:
                            sortGenerator = insertionSortSteps(actionQueue)
                            sortTimer = 0
                            sortActiveIndex = None
                        else:
                            # Nobody queued an action: nothing to sort, but the round still has to end.
                            resolveGenerator = resolveActionSteps(actionQueue)
                            resolveTimer = 0
                            currentTurnAction = None
                elif event.key == pygame.K_s:
                    _stepBattleSpeed()
                elif event.key == pygame.K_n:
                    newTurn(sprites)
                    pendingButtonIndex = None

        # ---------- Top-left icons: pause / save / load (each blocks or acts right away) ----------
        if hudAction is not None:
            action, hudAction = hudAction, None
            if action == "pause":
                choice = runPauseMenu(window, clock, FPS)
                if choice == "quit":
                    return "quit"
                if choice == "menu":
                    return "menu"
            elif action in ("save", "load"):
                if (onSave if action == "save" else onLoad) is None:
                    showToast(action.upper() + " UNAVAILABLE")
                else:
                    slot = runSlotMenu(window, clock, FPS, action, saves.allSlotInfo())
                    if slot == "quit":
                        return "quit"
                    if slot is not None:
                        if action == "save":
                            answer = True
                            if saves.slotInfo(slot) is not None:
                                answer = runConfirm(window, clock, FPS, f"OVERWRITE SLOT {slot}?",
                                                    ("The existing save will be replaced.",
                                                     "Only stage progress and settings are saved."),
                                                    "OVERWRITE", "CANCEL")
                            if answer is None:
                                return "quit"
                            if answer:
                                showToast(f"SAVED TO SLOT {slot}" if onSave(slot) else "SAVE FAILED")
                        else:
                            answer = runConfirm(window, clock, FPS, f"LOAD SLOT {slot}?",
                                                ("This battle will be abandoned.",
                                                 "Progress returns to that save."),
                                                "LOAD", "CANCEL")
                            if answer is None:
                                return "quit"
                            if answer:
                                if onLoad(slot):
                                    return "load"
                                showToast("LOAD FAILED")

        # ---------- Camera present and HUD ----------
        CAMERA.present(window, cameraZoom, cameraFocus)
        if bossFx is not None:
            bossFx.apply(window, dt)      # before the HUD so cards and buttons stay clean

        # Skill cards are drawn in screen space.
        if selectedSprite is not None and pendingButtonIndex is None:
            drawSkillButtons(window, selectedSprite, SKILL_ICONS, mousePos,
                             cameraZoom, cameraFocus, CAMERA.pan)

        # HUD elements are screen-space, not part of the world.
        if actionQueue:
            if sortGenerator is not None:
                queueActiveIndex = sortActiveIndex
            elif resolveGenerator is not None:
                queueActiveIndex = 0
            else:
                queueActiveIndex = None
            drawActionQueue(window, actionQueue, activeIndex=queueActiveIndex, icons=SKILL_ICONS)

        drawBossHpBar(window, sprites)      # after the queue, and positioned below it, so it never covers the tabs
        drawRoundInfo(window, roundNumber, screen_width)

        # ---------- Speed selector + end-turn prompt ----------
        hudMouse = pygame.mouse.get_pos()
        speedRects = drawSpeedControl(window, _battleSpeed[0], hudMouse, top=68) if battleResult is None else []
        iconRects = drawHudIcons(window, hudMouse) if battleResult is None else {}
        # KANA only appears once every living unit on your team has an action locked in
        canEndTurn = (battleResult is None and sortGenerator is None
                      and resolveGenerator is None and coinAnim is None
                      and allPlayersActed(sprites)
                      and any(currentSprite["side"] == "left" and not currentSprite["dead"] for currentSprite in sprites))
        if canEndTurn:
            endTurnRect = drawEndTurnPrompt(window, hudMouse)
        else:
            endTurnRect = None
        if tutorialGuide is not None:
            tutorialGuide.update({
                "sprites": sprites, "selected": selectedSprite, "pending": pendingButtonIndex,
                "queue": actionQueue, "round": roundNumber, "result": battleResult,
                "busy": (sortGenerator is not None or resolveGenerator is not None or coinAnim is not None
                         or skillAnim is not None or pendingEffectAction is not None),
                "endTurnRect": endTurnRect, "view": (cameraZoom, cameraFocus, CAMERA.pan),
            }, rawDt)
            tutorialGuide.draw(window)
        # Small "Battle Log ^" tab while skills are being picked.
        turnsActive = (sortGenerator is not None or resolveGenerator is not None or coinAnim is not None
                       or skillAnim is not None or pendingEffectAction is not None)
        drawBattleLog(window, battleLog, screen_width, screen_height, dt, compact=not turnsActive)
        drawBattleResult(window, battleResult, screen_width, screen_height,
                         elapsed=resultElapsed, subtitle=stageLabel, rounds=roundNumber)
        drawFps(window, clock)

        pygame.display.update()

    return "quit"


# ---------- Standalone test run ----------
if __name__ == "__main__":
    pygame.init()
    _window = pygame.display.set_mode((1284, 702))
    pygame.display.set_caption("Battle")
    _chapter = sys.argv[1] if len(sys.argv) > 1 else "Barangay"
    _stage = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 0
    print("Result:", runBattle(_window, _chapter, _stage))
    pygame.quit()
    sys.exit()