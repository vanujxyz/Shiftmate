"""One-off helper (milestone 2): add alert, idle, insight and reason strings to the locale files.

Kept in the repo so the source of these strings is traceable; re-running is idempotent.
"""

import json
from pathlib import Path

LOCALES = Path(__file__).resolve().parents[1] / "frontend" / "packages" / "i18n" / "src" / "locales"

# alert.<key>: (title, action, speak) per language, in order en, hi, ta
ALERTS = {
    "seatbelt_moving": [
        ("Seatbelt off while working", "Stop the machine. Buckle up.", "Stop. Seatbelt off."),
        ("काम के दौरान बेल्ट खुली है", "मशीन रोकिए। बेल्ट लगाइए।", "रुकिए। बेल्ट खुली है।"),
        ("வேலை செய்யும்போது பெல்ட் போடவில்லை", "இயந்திரத்தை நிறுத்துங்கள். பெல்ட் போடுங்கள்.", "நிறுத்துங்கள். பெல்ட் போடவில்லை."),
    ],
    "proximity_caution": [
        ("Person near the machine", "Keep watching. Slow your swing.", "Person near the machine."),
        ("मशीन के पास कोई है", "नज़र रखिए। घुमाव धीमा कीजिए।", "मशीन के पास कोई है।"),
        ("இயந்திரத்துக்கு அருகில் ஒருவர் இருக்கிறார்", "கவனமாகப் பாருங்கள். மெதுவாகச் சுழற்றுங்கள்.", "இயந்திரத்துக்கு அருகில் ஒருவர்."),
    ],
    "proximity_danger": [
        ("Person close to the swing zone", "Slow down. Do not swing that way.", "Person close. Slow down."),
        ("घुमाव के दायरे के पास कोई है", "धीरे चलाइए। उस तरफ़ मत घुमाइए।", "कोई पास है। धीरे चलाइए।"),
        ("சுழலும் பகுதிக்கு அருகில் ஒருவர்", "மெதுவாக. அந்தப் பக்கம் சுழற்ற வேண்டாம்.", "அருகில் ஒருவர். மெதுவாக."),
    ],
    "proximity_critical": [
        ("Person inside the swing zone", "Stop all movement now.", "Stop. Person in swing zone."),
        ("घुमाव के दायरे में कोई है", "तुरंत सब रोक दीजिए।", "रुकिए। दायरे में कोई है।"),
        ("சுழலும் பகுதிக்குள் ஒருவர் இருக்கிறார்", "உடனே எல்லா இயக்கத்தையும் நிறுத்துங்கள்.", "நிறுத்துங்கள். உள்ளே ஒருவர்."),
    ],
    "speed_near_person": [
        ("Moving fast near a person", "Stop. Let them move clear.", "Stop. Person near your path."),
        ("किसी के पास तेज़ चल रहे हैं", "रुकिए। उन्हें हटने दीजिए।", "रुकिए। रास्ते के पास कोई है।"),
        ("அருகில் ஆள் இருக்கும்போது வேகம் அதிகம்", "நிறுத்துங்கள். அவர் விலகட்டும்.", "நிறுத்துங்கள். பாதையில் ஒருவர்."),
    ],
    "unattended_running": [
        ("Engine on, cab empty", "Switch off before stepping out.", "Engine on with the cab empty."),
        ("इंजन चालू है, केबिन खाली है", "उतरने से पहले इंजन बंद कीजिए।", "इंजन चालू है, केबिन खाली है।"),
        ("இன்ஜின் ஓடுகிறது, கேபின் காலி", "இறங்கும் முன் இன்ஜினை அணையுங்கள்.", "இன்ஜின் ஓடுகிறது, கேபின் காலி."),
    ],
    "fatigue_warn": [
        ("Long time without a break", "Plan a short break soon.", "Time for a short break soon."),
        ("काफ़ी देर से ब्रेक नहीं हुआ", "जल्द ही एक छोटा ब्रेक लीजिए।", "जल्द ही छोटा ब्रेक लीजिए।"),
        ("நீண்ட நேரமாக இடைவேளை இல்லை", "விரைவில் ஒரு சிறிய இடைவேளை எடுங்கள்.", "விரைவில் சிறிய இடைவேளை எடுங்கள்."),
    ],
    "fatigue_limit": [
        ("Very long time without a break", "Park safely and take a break now.", "Please take a break now."),
        ("बहुत देर से ब्रेक नहीं हुआ", "मशीन सुरक्षित जगह खड़ी करके अभी ब्रेक लीजिए।", "अभी ब्रेक लीजिए।"),
        ("மிக நீண்ட நேரமாக இடைவேளை இல்லை", "இயந்திரத்தைப் பாதுகாப்பாக நிறுத்தி இப்போதே இடைவேளை எடுங்கள்.", "இப்போது இடைவேளை எடுங்கள்."),
    ],
    "heat_no_break": [
        ("Hot today, and no break for a while", "A water break now helps you finish strong.", "Hot today. Time for a water break."),
        ("आज गर्मी ज़्यादा है, काफ़ी देर से ब्रेक नहीं हुआ", "अभी पानी का ब्रेक लेने से आगे का काम आसान रहेगा।", "गर्मी है। पानी का ब्रेक लीजिए।"),
        ("இன்று வெயில் அதிகம், நீண்ட நேரமாக இடைவேளை இல்லை", "இப்போது தண்ணீர் இடைவேளை எடுத்தால் மீதி வேலை எளிதாகும்.", "வெயில் அதிகம். தண்ணீர் இடைவேளை."),
    ],
    "risk_band_raised": [
        ("Risk level raised", "Warning distances are wider now. Take extra care.", "Risk raised. Take extra care."),
        ("जोखिम बढ़ा है", "चेतावनी की दूरी अब ज़्यादा है। ज़्यादा ध्यान रखिए।", "जोखिम बढ़ा है। ध्यान रखिए।"),
        ("ஆபத்து நிலை உயர்ந்துள்ளது", "எச்சரிக்கை தூரம் இப்போது அதிகம். கூடுதல் கவனம் தேவை.", "ஆபத்து உயர்வு. கவனமாக இருங்கள்."),
    ],
    "risk_band_high": [
        ("Risk level high", "Slow down and keep a wider gap around the machine.", "Risk high. Slow down."),
        ("जोखिम ज़्यादा है", "धीरे चलाइए और मशीन के चारों ओर ज़्यादा जगह रखिए।", "जोखिम ज़्यादा है। धीरे चलाइए।"),
        ("ஆபத்து நிலை அதிகம்", "மெதுவாக இயக்குங்கள், இயந்திரத்தைச் சுற்றி அதிக இடைவெளி வையுங்கள்.", "ஆபத்து அதிகம். மெதுவாக."),
    ],
    "proximity_stale": [
        ("People sensing is off", "Look around before you swing.", "People sensing is off. Look around."),
        ("लोगों की पहचान बंद है", "घुमाने से पहले चारों ओर देखिए।", "पहचान बंद है। चारों ओर देखिए।"),
        ("ஆட்களைக் கண்டறிதல் வேலை செய்யவில்லை", "சுழற்றும் முன் சுற்றிலும் பாருங்கள்.", "கண்டறிதல் இல்லை. சுற்றிப் பாருங்கள்."),
    ],
}

# <namespace>.<key>: (en, hi, ta)
SIMPLE = {
    "idle": {
        "SCHEDULED_BREAK": ("Break", "ब्रेक", "இடைவேளை"),
        "WARM_UP": ("Warm-up", "वार्म-अप", "இன்ஜின் சூடாக்குதல்"),
        "UNATTENDED_RUNNING": ("Engine on, cab empty", "इंजन चालू, केबिन खाली", "இன்ஜின் ஓடுகிறது, கேபின் காலி"),
        "WAITING_FOR_TRUCK": ("Waiting for a truck", "ट्रक का इंतज़ार", "லாரிக்காகக் காத்திருப்பு"),
        "HABIT": ("Short stops", "छोटे ठहराव", "சிறு நிறுத்தங்கள்"),
        "UNKNOWN": ("Not sure", "पक्का नहीं", "உறுதியாகத் தெரியவில்லை"),
    },
    "insight": {
        "idle_ratio_high": ("Idle share was {{value}}, your usual is {{usual}}.", "खाली समय का हिस्सा {{value}} रहा, आम तौर पर {{usual}} रहता है।", "சும்மா இருந்த நேரப் பங்கு {{value}}, வழக்கமாக {{usual}}."),
        "fuel_per_load_high": ("Fuel per truck was {{value}}, your usual is {{usual}}.", "हर ट्रक पर ईंधन {{value}} लगा, आम तौर पर {{usual}} लगता है।", "ஒவ்வொரு லாரிக்கும் எரிபொருள் {{value}}, வழக்கமாக {{usual}}."),
        "fuel_rate_high": ("Fuel use was {{value}} an hour, your usual is {{usual}}.", "ईंधन खपत {{value}} प्रति घंटा रही, आम तौर पर {{usual}} रहती है।", "மணிக்கு எரிபொருள் செலவு {{value}}, வழக்கமாக {{usual}}."),
        "productivity_low": ("Loads per hour were {{value}}, your usual is {{usual}}.", "हर घंटे {{value}} लोड हुए, आम तौर पर {{usual}} होते हैं।", "மணிக்கு {{value}} லோடு, வழக்கமாக {{usual}}."),
        "seatbelt_unfastened": ("Seatbelt was off for {{value}} while working.", "काम के दौरान बेल्ट {{value}} तक खुली रही।", "வேலையின்போது பெல்ட் {{value}} போடப்படவில்லை."),
        "speed_high": ("Top travel speed was {{value}}, your usual is {{usual}}.", "सबसे तेज़ रफ़्तार {{value}} रही, आम तौर पर {{usual}} रहती है।", "அதிகபட்ச வேகம் {{value}}, வழக்கமாக {{usual}}."),
        "close_calls_high": ("People came close {{value}} times, your usual is {{usual}}.", "लोग {{value}} बार पास आए, आम तौर पर {{usual}} बार आते हैं।", "ஆட்கள் {{value}} முறை அருகில் வந்தனர், வழக்கமாக {{usual}} முறை."),
        "short_stops_high": ("Short stops added up to {{value}}, your usual is {{usual}}.", "छोटे ठहराव कुल {{value}} रहे, आम तौर पर {{usual}} रहते हैं।", "சிறு நிறுத்தங்கள் மொத்தம் {{value}}, வழக்கமாக {{usual}}."),
        "cab_empty_engine_on": ("Engine ran {{value}} with the cab empty.", "केबिन खाली था और इंजन {{value}} चला।", "கேபின் காலியாக இருந்தபோது இன்ஜின் {{value}} ஓடியது."),
        "rpm_high": ("Engine speed averaged {{value}}, your usual is {{usual}}.", "इंजन की औसत रफ़्तार {{value}} रही, आम तौर पर {{usual}} रहती है।", "இன்ஜின் சராசரி வேகம் {{value}}, வழக்கமாக {{usual}}."),
    },
    "reason": {
        "wet_ground_slower": ("Wet ground adds time", "गीली ज़मीन से समय बढ़ेगा", "ஈரமான தரையால் நேரம் கூடும்"),
        "dry_ground_faster": ("Firm ground saves time", "पक्की ज़मीन से समय बचेगा", "உறுதியான தரையால் நேரம் மிச்சம்"),
        "rain_slower": ("Rain adds time", "बारिश से समय बढ़ेगा", "மழையால் நேரம் கூடும்"),
        "experience_slower": ("Less practice on this task, allow more time", "यह काम कम बार किया है, समय ज़्यादा लग सकता है", "இந்த வேலையில் பயிற்சி குறைவு, நேரம் அதிகம் ஆகலாம்"),
        "experience_faster": ("Your experience saves time", "आपके अनुभव से समय बचेगा", "உங்கள் அனுபவத்தால் நேரம் மிச்சம்"),
        "truck_supply_slower": ("Fewer trucks expected, adds time", "कम ट्रक आने की उम्मीद, समय बढ़ेगा", "குறைவான லாரிகள் வரும், நேரம் கூடும்"),
        "truck_supply_faster": ("Good truck supply saves time", "ट्रक अच्छे मिलेंगे, समय बचेगा", "போதுமான லாரிகள், நேரம் மிச்சம்"),
        "heat_slower": ("Heat adds time", "गर्मी से समय बढ़ेगा", "வெயிலால் நேரம் கூடும்"),
        "cool_faster": ("Cool weather saves time", "ठंडे मौसम से समय बचेगा", "குளிர்ந்த வானிலையால் நேரம் மிச்சம்"),
        "night_slower": ("Working in the dark adds time", "अँधेरे में काम से समय बढ़ेगा", "இருட்டில் வேலை செய்வதால் நேரம் கூடும்"),
        "daylight_faster": ("Daylight saves time", "दिन की रोशनी से समय बचेगा", "பகல் வெளிச்சத்தால் நேரம் மிச்சம்"),
        "quantity_large": ("Large quantity", "मात्रा ज़्यादा है", "அளவு அதிகம்"),
        "quantity_small": ("Small quantity", "मात्रा कम है", "அளவு குறைவு"),
        "task_type_slower": ("This kind of task takes longer", "इस तरह के काम में ज़्यादा समय लगता है", "இந்த வகை வேலைக்கு அதிக நேரம் ஆகும்"),
        "task_type_faster": ("This kind of task is quicker", "इस तरह का काम जल्दी होता है", "இந்த வகை வேலை விரைவாக முடியும்"),
        "machine_slower": ("This machine is slower for this task", "इस काम के लिए यह मशीन धीमी है", "இந்த வேலைக்கு இந்த இயந்திரம் மெதுவானது"),
        "machine_faster": ("This machine suits the task", "यह मशीन इस काम के लिए सही है", "இந்த இயந்திரம் இந்த வேலைக்கு ஏற்றது"),
        "site_slower": ("Site conditions add time", "साइट की हालत से समय बढ़ेगा", "தள நிலைமையால் நேரம் கூடும்"),
        "site_faster": ("Site conditions save time", "साइट की हालत से समय बचेगा", "தள நிலைமையால் நேரம் மிச்சம்"),
        "time_of_day_slower": ("Time of day adds time", "दिन के इस समय काम धीमा होता है", "இந்த நேரத்தில் வேலை மெதுவாக நடக்கும்"),
        "time_of_day_faster": ("Good time of day for this task", "इस काम के लिए यह अच्छा समय है", "இந்த வேலைக்கு இது நல்ல நேரம்"),
    },
}

for index, lang in enumerate(["en", "hi", "ta"]):
    path = LOCALES / f"{lang}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["alert"] = {
        key: dict(zip(("title", "action", "speak"), texts[index], strict=True))
        for key, texts in ALERTS.items()
    }
    for namespace, entries in SIMPLE.items():
        data[namespace] = {key: texts[index] for key, texts in entries.items()}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("locales updated")
