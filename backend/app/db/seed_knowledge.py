from datetime import datetime, timezone
import uuid
import sys
from pathlib import Path

# Ensure backend in path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.session import SessionLocal
from app.models import DiseaseKnowledge

KNOWLEDGE_ENTRIES = [
    # 1. HEALTHY (EN)
    {
        "disease_class": "Healthy",
        "language_code": "en",
        "display_name": "Healthy Sugarcane",
        "scientific_name": "Saccharum officinarum",
        "symptoms": "Vigorous, dark green foliage with uniform leaf blades. No chlorotic lesions, midrib discoloration, or necrotic spots. Stalk vascular bundles are clean and moist.",
        "preventive_guidance": "Maintain balanced N-P-K nutrition (275:60:110 kg/ha in splits). Follow recommended furrow spacing (90-120 cm) and timely earthing-up.",
        "monitoring_guidance": "Conduct weekly field walks examining 20 random stools per acre. Check upper, middle, and lower canopy leaves for early signs of pest or fungal stress.",
        "management_guidance": "Continue optimal crop management: schedule irrigation based on soil moisture, apply organic trash mulching, and practice weed sanitation.",
        "source_reference": "ICAR - Sugarcane Breeding Institute (SBI) Agronomy Guidelines"
    },
    # 1. HEALTHY (TA)
    {
        "disease_class": "Healthy",
        "language_code": "ta",
        "display_name": "ஆரோக்கியமான கரும்பு",
        "scientific_name": "Saccharum officinarum",
        "symptoms": "வளர்ச்சியான அடர்ந்த பச்சை நிற இலைகள்; சீரான இலை விளிம்புகள். புள்ளிகள், நரம்பு வெளிர்தல் அல்லது திசு அழுகல் அறிகுறிகள் இல்லை.",
        "preventive_guidance": "பரிந்துரைக்கப்பட்ட தழை, மணி, சாம்பல் சத்துக்களை (275:60:110 கிலோ/ஹெக்டர்) சரியான இடைவெளியில் இடவும். 90-120 செ.மீ பார் இடைவெளியைப் பராமரிக்கவும்.",
        "monitoring_guidance": "வாரம் ஒரு முறை வயல் ஆய்வு செய்து, ஏக்கருக்கு 20 தூர்களைக் கவனிக்கவும். பூச்சி அல்லது பூஞ்சை அறிகுறிகளை முன்கூட்டியே கண்டறியவும்.",
        "management_guidance": "வழக்கமான சாகுபடி முறைகளைத் தொடரவும்: சரியான பாசனம், சோகை உரித்தல் மற்றும் உலர் சாகுபடி முறைகளைப் பின்பற்றவும்.",
        "source_reference": "ICAR - கரும்பு இனப்பெருக்க நிறுவனம் (SBI) வழிகாட்டுதல்"
    },
    # 2. RED ROT (EN)
    {
        "disease_class": "RedRot",
        "language_code": "en",
        "display_name": "Red Rot",
        "scientific_name": "Colletotrichum falcatum (Glomerella tucumanensis)",
        "symptoms": "Third or fourth leaf from the crown displays yellowing and tip drying. Midrib exhibits elongated blood-red lesions with characteristic white horizontal transverse patches. Splitting the cane reveals internal red pith discoloration with alcohol/sour odor.",
        "preventive_guidance": "Use certified seed setts from disease-free nurseries. Treat setts with hot water at 52°C for 30 minutes. Select resistant varieties (e.g., Co 86032, Co 09004, Co 11015). Avoid continuous ratooning in infected fields.",
        "monitoring_guidance": "Intensify scouting during monsoon (July-September). Inspect leaf midribs for reddish lesions and look for sudden spindle drying in localized patches.",
        "management_guidance": "Rogue out and destroy infected stools immediately. Dip setts in Carbendazim 50% WP (1 g/L) or Trichoderma viride (10 g/L) for 15 minutes before planting. Ensure field drainage to prevent water stagnation.",
        "source_reference": "ICAR-SBI Pathology Monograph on Sugarcane Red Rot"
    },
    # 2. RED ROT (TA)
    {
        "disease_class": "RedRot",
        "language_code": "ta",
        "display_name": "செவ்வழுகல் நோய்",
        "scientific_name": "Colletotrichum falcatum",
        "symptoms": "மேலிருந்து 3 அல்லது 4-வது இலை மஞ்சளாகி முனைகள் காய்ந்துவிடும். நடு நரம்பில் இரத்த சிவப்பு நிறப் புள்ளிகளும், குறுக்கே வெண்மையான திட்டுக்களும் தோன்றும். கரும்பைப் பிளந்து பார்த்தால் உட்பகுதி சிவந்து சாராய வாசனை வீசும்.",
        "preventive_guidance": "நோய் தாக்காத சான்றளிக்கப்பட்ட விதைக்கரணைகளைப் பயன்படுத்தவும். கரணைகளை 52°C சுடுநீரில் 30 நிமிடங்கள் நேர்த்தி செய்யவும். நோய் எதிர்ப்புத் திறன் கொண்ட ரகங்களை (Co 86032, Co 09004) பயிரிடவும்.",
        "monitoring_guidance": "மழைக்காலத்தில் (ஜூலை-செப்டம்பர்) நடுநரம்பின் நிறமாற்றத்தை உன்னிப்பாகக் கவனிக்கவும். திடீரென இலைகள் காய்வதைக் கண்காணிக்கவும்.",
        "management_guidance": "பாதிக்கப்பட்ட கரும்புகளை வேரோடு பிடுங்கி தீயிட்டு அழிக்கவும். கார்பென்டாசிம் (1 கிராம்/லிட்டர்) அல்லது ட்ரைக்கோடெர்மா விரிடி (10 கிராம்/லிட்டர்) கரைசலில் விதைக்கரணைகளை 15 நிமிடம் நனைத்து நடவும்.",
        "source_reference": "ICAR-SBI கரும்பு நோயியல் ஆராய்ச்சி குறிப்பேடு"
    },
    # 3. RUST (EN)
    {
        "disease_class": "Rust",
        "language_code": "en",
        "display_name": "Sugarcane Rust",
        "scientific_name": "Puccinia melanocephala",
        "symptoms": "Minute, elongated, chlorotic yellowish flecks on both surfaces of young leaves. Lesions enlarge and turn orange-brown to reddish-brown raised pustules that rupture, releasing powdery brown urediniospores.",
        "preventive_guidance": "Avoid excessive nitrogenous fertilizer application which fosters lush susceptible tissues. Avoid dense plant populations; ensure ample sunlight penetration and airflow.",
        "monitoring_guidance": "Monitor lower and middle canopy leaves during cool, humid weather (20°C-26°C with relative humidity > 75% and heavy dew).",
        "management_guidance": "Spray Mancozeb 75% WP (2.0 g/L) or Propiconazole 25% EC (1.0 ml/L) at the onset of initial pustules. Repeat application after 14-21 days if cloudy and humid conditions persist.",
        "source_reference": "TNAU Agritech Portal & ICAR Cane Pathology"
    },
    # 3. RUST (TA)
    {
        "disease_class": "Rust",
        "language_code": "ta",
        "display_name": "துரு நோய்",
        "scientific_name": "Puccinia melanocephala",
        "symptoms": "இலைகளின் இருபுறமும் சிறிய மஞ்சள் நிறப் புள்ளிகள் தோன்றும். பின்னர் அவை நீளவாக்கில் பழுப்பு-ஆரஞ்சு நிறத் திட்டுக்களாக மாறி, வெடித்து பழுப்பு நிறப் பொடி போன்ற வித்துக்களை வெளியிடும்.",
        "preventive_guidance": "அதிகப்படியான தழைச்சத்தைத் தவிர்க்கவும். நெருக்கமாக நடவு செய்யாமல், நல்ல காற்றோட்டம் மற்றும் சூரிய ஒளி படும்படி பார்த்துக் கொள்ளவும்.",
        "monitoring_guidance": "குளிர்ந்த, ஈரப்பதம் மிகுந்த வானிலையில் (20°C-26°C, 75% மேல் ஈரப்பதம்) கீழ் மற்றும் நடுமட்ட இலைகளைத் தீவிரமாகக் கண்காணிக்கவும்.",
        "management_guidance": "அறிகுறிகள் தென்பட்டவுடன் மேன்கோசெப் 75% WP (2 கிராம்/லிட்டர்) அல்லது புரோபிகோனசோல் 25% EC (1 மி.லி/லிட்டர்) தெளிக்கவும். தேவைப்பட்டால் 15 நாட்கள் கழித்து மீண்டும் தெளிக்கவும்.",
        "source_reference": "தமிழ்நாடு வேளாண்மைப் பல்கலைக்கழகம் (TNAU) பயிர் பாதுகாப்பு"
    },
    # 4. MOSAIC (EN)
    {
        "disease_class": "Mosaic",
        "language_code": "en",
        "display_name": "Sugarcane Mosaic",
        "scientific_name": "Sugarcane Mosaic Virus (SCMV)",
        "symptoms": "Contrasting patterns of alternating dark green and pale green/yellowish chlorotic streaks along the leaf blade. Symptoms are most conspicuous at the base of young rapidly growing leaves.",
        "preventive_guidance": "Use disease-free seed canes from apical meristem tissue culture. Eliminate grassy weed hosts (Sorghum halepense, Echinochloa) around field bunds.",
        "monitoring_guidance": "Scout young shoots during formative stage (30-90 days after planting). Inspect leaf whorls in morning light for mosaic mottling.",
        "management_guidance": "Rogue out infected stools in early stages. Control aphid vector (Rhopalosiphum maidis) populations using Imidacloprid 17.8% SL (0.3 ml/L) or 3% Neem seed kernel extract.",
        "source_reference": "ICAR-SBI Plant Virology Division"
    },
    # 4. MOSAIC (TA)
    {
        "disease_class": "Mosaic",
        "language_code": "ta",
        "display_name": "தேமல் நோய் (மொசைக்)",
        "scientific_name": "Sugarcane Mosaic Virus (SCMV)",
        "symptoms": "இலையின் நரம்புகளுக்கு இடையே வெளிர் பச்சை மற்றும் அடர் பச்சை நிறத்தில் மாறி மாறி தேமல் போன்ற திட்டுகள் காணப்படும். இளம் இலைகளின் அடிப்பகுதியில் இது தெளிவாகத் தெரியும்.",
        "preventive_guidance": "திசு வளர்ப்பு முறையில் பெறப்பட்ட தூய விதைக்கரணைகளைப் பயன்படுத்தவும். வயல் வரப்புகளில் உள்ள புல் வகை களைகளை முழுமையாக அகற்றவும்.",
        "monitoring_guidance": "பயிரின் ஆரம்ப வளர்ச்சிப் பருவத்தில் (30-90 நாட்கள்) இளம் இலைகளைக் கூர்ந்து கவனிக்கவும்.",
        "management_guidance": "தாக்கப்பட்ட இளம் பயிர்களை உடனே பிடுங்கி எரிக்கவும். அசுவினி பூச்சிகளைக் கட்டுப்படுத்த இமிடாக்ளோப்ரிட் 17.8% SL (0.3 மி.லி/லிட்டர்) அல்லது வேப்பங்கொட்டை சாறு 5% தெளிக்கவும்.",
        "source_reference": "ICAR-SBI கரும்பு தீநுண்மவியல் பிரிவு"
    },
    # 5. YELLOW (EN)
    {
        "disease_class": "Yellow",
        "language_code": "en",
        "display_name": "Yellow Leaf Disease (YLD)",
        "scientific_name": "Sugarcane Yellow Leaf Virus (SCYLV)",
        "symptoms": "Distinct yellowing of the leaf midrib on the 3rd to 6th leaves from top, gradually extending into the lamina. Lamina turns bright yellow while midrib remains chlorotic; in advanced stages, leaf tips dry with bunchy top appearance.",
        "preventive_guidance": "Plant virus-tested tissue-culture plantlets. Maintain optimal potassium fertilization (120-150 kg/ha K2O) to strengthen vascular resilience. Avoid ratoon propagation from infected blocks.",
        "monitoring_guidance": "Scout mature canes from 5th to 8th month. Inspect underside of leaf midribs for bright yellow discoloration.",
        "management_guidance": "Apply prophylactic systemic vector control against the sugarcane aphid (Melanaphis sacchari) using Dimethoate 30% EC (1.5 ml/L) or Thiamethoxam 25% WG (0.25 g/L). Maintain consistent soil moisture during formative phases.",
        "source_reference": "ICAR-SBI Pathology Advisory on Yellow Leaf Disease"
    },
    # 5. YELLOW (TA)
    {
        "disease_class": "Yellow",
        "language_code": "ta",
        "display_name": "மஞ்சள் இலை நோய்",
        "scientific_name": "Sugarcane Yellow Leaf Virus (SCYLV)",
        "symptoms": "மேலிருந்து 3 முதல் 6-வது இலைகளின் நடுநரம்பின் அடிப்பகுதி பிரகாசமான மஞ்சள் நிறமாக மாறும். பின்னர் இலைப்பரப்பு முழுவதும் மஞ்சளாகி, முனைகள் கருகும். முதிர்ந்த கரும்புகளில் வளர்ச்சி குன்றி தண்டு மெலியும்.",
        "preventive_guidance": "தீநுண்மம் இல்லாத தரமான திசு வளர்ப்பு கன்றுகளைப் பயன்படுத்தவும். சாம்பல் சத்தை (பொட்டாஷ்) பரிந்துரைக்கப்பட்ட அளவில் இடவும். பாதிக்கப்பட்ட வயல்களில் மறுதாம்புப் பயிரைத் தவிர்க்கவும்.",
        "monitoring_guidance": "5 முதல் 8-வது மாதங்களில் கரும்பின் நடுநரம்பின் அடிப்பகுதியை ஆய்வு செய்து மஞ்சள் நிறமாற்றத்தைக் கண்காணிக்கவும்.",
        "management_guidance": "நோய் பரப்பும் கரும்பு அசுவினியைக் கட்டுப்படுத்த தையமீதாக்ஸம் 25% WG (0.25 கிராம்/லிட்டர்) அல்லது டைமித்தோயேட் (1.5 மி.லி/லிட்டர்) தெளிக்கவும். போதிய நீர்ப்பாசனம் வழங்கி பயிர் வறட்சியைத் தவிர்க்கவும்.",
        "source_reference": "ICAR-SBI மஞ்சள் இலை நோய் மேலாண்மை வழிகாட்டி"
    }
]

def seed():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    added = 0
    updated = 0
    try:
        for entry in KNOWLEDGE_ENTRIES:
            existing = db.query(DiseaseKnowledge).filter_by(
                disease_class=entry["disease_class"],
                language_code=entry["language_code"]
            ).first()
            if existing:
                for k, v in entry.items():
                    setattr(existing, k, v)
                existing.updated_at = now
                existing.last_reviewed_at = now
                existing.is_published = True
                updated += 1
            else:
                record = DiseaseKnowledge(
                    id=str(uuid.uuid4()),
                    last_reviewed_at=now,
                    is_published=True,
                    updated_at=now,
                    **entry
                )
                db.add(record)
                added += 1
        db.commit()
        print(f"Successfully seeded Disease Knowledge Base: {added} added, {updated} updated.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()

