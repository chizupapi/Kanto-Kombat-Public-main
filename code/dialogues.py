# =====================================================================================================
#  DIALOGUES -- every line of talking in the Chapter 1 story scenes
# =====================================================================================================
#  A line is one dictionary:   {"name": "Darit", "text": "what he says"}
#    name   who is speaking. It must be a key of CHARACTERS in scenes.py (Darit, Sandugo, Otab) to show a
#           portrait and put the name tag on that character's side. Use " " (a space) for narration:
#           nobody lights up as the speaker and the name tag is blank.
#    text   the words shown in the dialogue box (it wraps automatically). Keep it to about 3 lines.
#
#  WHICH LIST PLAYS WHEN (the story order):
#    DIALOGUES        parts 1 AND 2 in one list. scenes.CONTINUATION_START (8) is where part 2 begins,
#                     so the first 8 lines are part 1 and the rest are part 2. Add a line before that
#                     number and you must raise CONTINUATION_START by one.
#    BG17_DIALOGUES   part 3 (after background 17)
#    BG18_DIALOGUES   part 4 (after background 18)
#    BG19_DIALOGUES   part 5 (after the Kanto Kombat animation, background 19)
#    BG20_DIALOGUES   part 6 (cutscene 3, after backgrounds 20-23)
#  Lines play top to bottom, one per click.
# =====================================================================================================

DIALOGUES = [

    # ========================================================
    # PART 1: BEFORE CUTSCENE 2
    # Entries 1-8
    # ========================================================

    {
        "name": "Darit",
        "text": "Oyy Sandugo, bat suot mo yung Sapatos ko?"
    },
    {
        "name": "Sandugo",
        "text": "ahh Preee, pahiram mo na sakin, ngayun lang naman"
    },
    {
        "name": "Darit",
        "text": "HAYY, ano gagamitin ko? naka paa lang ako ngayun"
    },
    {
        "name": "Sandugo",
        "text": "Dont worry pre, dala ko yung tsinelas ko ikaw muna mag suot"
    },
    {
        "name": "Darit",
        "text": "Hanepp, ako pa nawalan ng sapatos nagyun"
    },
    {
        "name": "Sandugo",
        "text": "Sige na pree, nakasuot na eh, hayaan mo na HAHAHA"
    },
    {
        "name": "Darit",
        "text": "Sigee na ngaa, basta palit na tayu mamayang uwian"
    },
    {
        "name": "Sandugo",
        "text": "GGGGG, dont worry erp"
    },

    # ========================================================
    # PART 2: AFTER CUTSCENE 2
    # ========================================================

    {
        "name": "Sandugo",
        "text": "HUHHH?, sino yun?"
    },
    {
        "name": "Darit",
        "text": "Huh? Saan pre?"
    },
    {
        "name": "Sandugo",
        "text": "ayun ohh yung parang ninja HAHAHA"
    },
    {
        "name": "Darit",
        "text": "Parang si hayabusa ehh, siuro akala nya quarantine days padin"
    },
    {
        "name": "Sandugo",
        "text": "Grabi ka naman, baka naman trip nya lang yan HAHAHA hayaan mo nalang"
    },
    {
        "name": "Darit",
        "text": "Ehh, sabagay"
    },
    {
        "name": "Sandugo",
        "text": "Wait pre try ko kausapin tas sabay natin pauwi"
    },
    {
        "name": "Darit",
        "text": "Sige dali ng makauwi na"
    },
    {
        "name": "Sandugo",
        "text": "UYY! pre"
    },

    # ========================================================
    # OTAB ENTERS
    # ========================================================

    {
        "name": "Otab",
        "text": "Huh? ayy hello"
    },
    {
        "name": "Sandugo",
        "text": "Grabi naman nahihiya kaba erp NYAHAHAHAH anyway bago ka lang ba dito?"
    },
    {
        "name": "Otab",
        "text": "Huh? ehh hindi pre di"
    },
    {
        "name": "Sandugo",
        "text": "Totoo ba? bat parang ngayun lang kita natanaw dito"
    },
    {
        "name": "Otab",
        "text": "Matagal na ko dito di nyo lang ako nararamdaman"
    },
    {
        "name": "Sandugo",
        "text": "Hmmmm? saang section ka pre?"
    },
    {
        "name": "Otab",
        "text": "Huh? di mo talaga ako nakikilala?"
    },
    {
        "name": "Sandugo",
        "text": "No offence pre, pero mahirap ka mamukaan lalu na pag naka mask"
    },
    {
        "name": "Otab",
        "text": "hahaha..., sabagay pero classmate mo ko"
    },
    {
        "name": "Sandugo",
        "text": "ANOOO, totoo ba pre hanep na yan bat di kita kilala"
    },
    {
        "name": "Otab",
        "text": "Ehh sabi ko nga pre mahirap ako maramdaman"
    },
    {
        "name": "Darit",
        "text": "Oyyy Sandugo katagal mo naman ano sasabay ba sya o hindi gusto ko na umuwi"
    },
    {
        "name": "Sandugo",
        "text": "Ay oo nga pala andyan ka pala HAHAHAHAH"
    },
    {
        "name": "Darit",
        "text": "Hanep naman ohhh"
    },
    {
        "name": "Sandugo",
        "text": "HEHEH bali pre ito si otab at pre ito si darit kaibigan ko na yan dati pa solid "
    },
    {
        "name": "Otab",
        "text": "Ayy hello"
    },
    {
        "name": "Darit",
        "text": "HEHEHE Hi"
    },
    {
        "name": "Darit",
        "text": "Okieee pre anu pre sabay kana samin uuwi na kami eh"
    },
    {
        "name": "Otab",
        "text": "Ahhh... sigi pre"
    },

]


# ========================================================
# PART 3: AFTER BACKGROUND 17
# ========================================================

BG17_DIALOGUES = [

    {
        "name": "Otab",
        "text": "sigi na mga pre hanggang dito nalang ako ingat kayu sa pag uwi at salamat sa pagsama sakin"
    },
    {
        "name": "Darit",
        "text": "Pre simula ngayun samin kana sasabay HAHAHAHA sawa na ko kay sandugo"
    },
    {
        "name": "Sandugo",
        "text": "Ayy TALAGA BA sawa nadin naman ako sayu at least may bago HAHAHAH sigii pre ingat"
    },
    {
        "name": "Darit",
        "text": "Ingat ka otab"
    },
    {
        "name": " ",
        "text": "Humiwalay na si otab sa dalawa"
    },
    {
        "name": "Darit",
        "text": "Ohh ano tayung dalawa nalang HAHAHA"
    },
    {
        "name": "Sandugo",
        "text": "Eh ano pa nga ba, ganun naman lagi eh"
    },
    {
        "name": " ",
        "text": "Naglakad na si dairt and Sandugo pauwi"
    },
    {
        "name": "Darit",
        "text": "Pre, nalala mo ba yung kwento ni aling rosita satin dati"
    },
    {
        "name": "Sandugo",
        "text": "Huh? di ko ata tanda yun"
    },
    {
        "name": "Darit",
        "text": "Yung tungkol dun sa white lady na lumilitaw dito sa kanto"
    },
    {
        "name": "Darit",
        "text": "Pre, nalala mo ba yung kwento ni aling rosita satin dati"
    },
    {
        "name": "Sandugo",
        "text": "Uyy pree wag ganyan hahah... di ako makakauwi nyan"
    },
    {
        "name": "Sandugo",
        "text": "HAHAHAHAA joke lang pre"
    },
    {
        "name": "Sandugo",
        "text": "HAYSSS ikaw talaga"
    },
    {
        "name": "  ",
        "text": "psstt"
    },
    {
        "name": "Darit",
        "text": "HUH?"
    },
    {
        "name": "Sandugo",
        "text": "HUH!"
    },
    {
        "name": "Darit",
        "text": "Takbo PREEE!!"
    },
    {
        "name": "  ",
        "text": "Mabilis nagsi takbo ang dalawa"
    },
    {
        "name": "Darit",
        "text": "HAHAHAHAAHAH"
    },
    {
        "name": "Sandugo",
        "text": "Ikaw kasi pre ehh mutik na tuloy magpakita yung white lady satin HAHAH"
    },
    {
        "name": "Darit",
        "text": "ayoko na pre di ko na uulitin HAHAHAHA"
    },
    {
        "name": "Darit",
        "text": "Pano bayan pre dito nalang ako, BYEEE"
    },
    {
        "name": "Sandugo",
        "text": "Sigi pre BYEEEE kita tayu bukas sa amin laro tayu"
    },
    {
        "name": "Darit",
        "text": "SIGII ingat ka pre"
    },

]

BG18_DIALOGUES = [
    {
        "name": "Darit",
        "text": "Hayssss, makapag hugas nanga pinggan"
    },
    {
        "name": " ",
        "text": "Habang nag huhugas ng plato"
    },
    {
        "name": "Darit",
        "text": "Ano ano pa kayang gamit pede ko dalhin bukas kila sandugo"
    },
]

# ---------- Background 19 Dialogues ----------
# Plays after the Kanto Kombat animation.

BG19_DIALOGUES = [
    {
        "name": "Darit",
        "text": "Huh? bat kadaming tao dun?"
    },
    {
        "name": "Darit",
        "text": "may nangyari ba?"
    },
    {
        "name": "Darit",
        "text": "HALA kila sandugo yun ahhh"
    },
   
]


# ========================================================
# PART 6: CUTSCENE 3 DIALOGUES
# After backgrounds 20–23
# ========================================================

BG20_DIALOGUES = [

    {
        "name": "Darit",
        "text": "Oyyy pre, ok ka lang ba"
    },
    {
        "name": "Sandugo",
        "text": "Mga hayup sila, sa amin itong lupa na ito pero pilit kaming pina alis"
    },
    {
        "name": "Darit",
        "text": "Wala talaga tayung ma aasahan sa sistema sa pinas pre"
    },
    {
        "name": "Sandugo",
        "text": "Magbabayd silang lahat WAHHHHHH"
    },

]

