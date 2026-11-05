import csv
import json
import re
from pathlib import Path

csv_path = Path("backend/app/data/raw_youtube_videos.csv")
output_path = Path("backend/app/data/university_videos.json")

# Curated list of 53 top-tier, high-production, authoritative videos
CURATED_CONFIG = {
    # 1. Campus Tour & Infrastructure
    "9kYIkkadZkU": {
        "category": "Campus Tour & Infrastructure",
        "keywords": ["campus", "campus tour", "tour", "infrastructure", "smart classrooms", "facilities", "buildings", "walkthrough", "drone", "green campus"]
    },
    "kSuE6XvxwSQ": {
        "category": "Campus Tour & Infrastructure",
        "keywords": ["campus", "campus tour", "tour", "overview", "south india", "facilities", "classrooms", "buildings"]
    },
    "ZPihQwl5it8": {
        "category": "Campus Tour & Infrastructure",
        "keywords": ["campus", "night view", "campus night", "peaceful", "cinematic", "lighting", "infrastructure", "evening"]
    },
    "SlVZqQqiOsg": {
        "category": "Campus Tour & Infrastructure",
        "keywords": ["campus", "eco-friendly", "green campus", "nature", "lush green", "trees", "environment", "surroundings"]
    },
    "e5PIni3cAOs": {
        "category": "Campus Tour & Infrastructure",
        "keywords": ["campus", "campus tour", "tour", "students react", "reaction", "review", "infrastructure", "walkthrough"]
    },
    "hysHzDeSc40": {
        "category": "Campus Tour & Infrastructure",
        "keywords": ["campus", "night view", "campus tour", "tour", "short tour", "aerial"]
    },

    # 2. Hostels & Dining
    "vf6DnDS83nw": {
        "category": "Hostels & Living",
        "keywords": ["hostel", "hostels", "hostel life", "rooms", "ac rooms", "accommodation", "dorm", "residential", "stay", "facilities"]
    },
    "rpRekBrnGYs": {
        "category": "Hostels & Living",
        "keywords": ["hostel", "hostels", "hostel food", "mess", "dining", "food quality", "canteen", "meals", "menu", "eating"]
    },
    "_dQ6W2sYXrw": {
        "category": "Hostels & Living",
        "keywords": ["hostel", "hostels", "hostel life", "campus living", "student stay", "hostel experience", "roommate", "curfew"]
    },
    "Nfe7N9TzJg4": {
        "category": "Hostels & Living",
        "keywords": ["hostel", "hostels", "hostel life", "home away from home", "rooms", "safety", "security", "living"]
    },
    "ITwoDHleH8g": {
        "category": "Hostels & Living",
        "keywords": ["hostel", "hostels", "girls hostel", "lumina", "hostel night", "celebration", "fun", "safety"]
    },
    "KuuTJHWw8H4": {
        "category": "Hostels & Living",
        "keywords": ["hostel", "hostels", "boys hostel", "lumina", "hostel night", "music", "memories", "hostel life"]
    },

    # 3. Placements & Top Packages
    "w6uDyZnrZYE": {
        "category": "Placements & Careers",
        "keywords": ["placement", "placements", "microsoft", "51 lpa", "highest package", "highest placement", "salary", "cse", "recruiter"]
    },
    "yKV31PjGuuQ": {
        "category": "Placements & Careers",
        "keywords": ["placement", "placements", "paypal", "34.4 lpa", "salary", "highest package", "jobs", "etv news", "tech"]
    },
    "wqBdUJ2PIbs": {
        "category": "Placements & Careers",
        "keywords": ["placement", "placements", "jpmorgan", "jp morgan", "19.75 lpa", "investment bank", "package", "cse", "recruiter"]
    },
    "xI_20ugBFPc": {
        "category": "Placements & Careers",
        "keywords": ["placement", "placements", "cisco", "25 lpa", "networking", "package", "hiring", "offers", "careers"]
    },
    "sYrFJkuZIOw": {
        "category": "Placements & Careers",
        "keywords": ["placement", "internship", "amazon", "above 1 lakh", "stipend", "cse", "career", "interview", "tech"]
    },
    "VWRrbJJ6pJ8": {
        "category": "Placements & Careers",
        "keywords": ["placement", "placements", "flipkart", "ece", "ecommerce", "recruiter", "success story", "career"]
    },
    "F_hHMoqGvsg": {
        "category": "Placements & Careers",
        "keywords": ["placement", "placements", "accenture", "it consulting", "recruiter", "success story", "jobs", "campus to corporate"]
    },
    "QGPZydHWiGs": {
        "category": "Placements & Careers",
        "keywords": ["placement", "placements", "dual placement", "capgemini", "oasis automation", "ece", "multiple offers"]
    },
    "il1kYdhiEIg": {
        "category": "Placements & Careers",
        "keywords": ["placement", "placements", "placement stats", "average package", "recruiters", "companies", "3 years", "statistics", "report"]
    },

    # 4. School of CS, AI & Robotics
    "ELFrtppGTlc": {
        "category": "CS, AI & Technology",
        "keywords": ["cs", "cse", "ai", "artificial intelligence", "school of cs and ai", "faculty", "academics", "teaching", "curriculum"]
    },
    "oFx9HUKmMc0": {
        "category": "CS, AI & Technology",
        "keywords": ["hackathon", "coding", "night hackathon", "programming", "cs", "ai", "12 hours", "developers", "coding challenge"]
    },
    "HY6ITFOrkCQ": {
        "category": "CS, AI & Technology",
        "keywords": ["microsoft", "industrial visit", "tech exposure", "industry visit", "real world", "corporate visit"]
    },
    "gtAKdshW7cQ": {
        "category": "CS, AI & Technology",
        "keywords": ["ai", "robotics", "interdisciplinary", "mechatronics", "labs", "automation", "hands on"]
    },
    "6CpaOKukDRU": {
        "category": "CS, AI & Technology",
        "keywords": ["machine learning", "ml", "ai", "faculty", "data science", "neural networks", "algorithms"]
    },
    "o5mNTb6_RM8": {
        "category": "CS, AI & Technology",
        "keywords": ["b.tech ai", "artificial intelligence", "free laptop", "placement guarantee", "btech", "cs"]
    },

    # 5. School of Agriculture
    "A_nZgBa_pGY": {
        "category": "School of Agriculture",
        "keywords": ["agriculture", "agri", "agriculture campus", "agri block", "labs", "greenhouse", "farm", "facilities", "tour"]
    },
    "qpUO0_1kdao": {
        "category": "School of Agriculture",
        "keywords": ["agriculture", "agri", "icar", "icar accreditation", "accredited", "b.sc agriculture", "degree validity"]
    },
    "1EUVC3_k94I": {
        "category": "School of Agriculture",
        "keywords": ["agriculture", "agri", "hands-on", "modern farming", "industry visits", "farming practices", "field work"]
    },
    "AMMg_mC_bCI": {
        "category": "School of Agriculture",
        "keywords": ["agriculture", "agri orientation", "vice chancellor", "sustainable agriculture", "future of farming"]
    },
    "CbE5QoE7IgE": {
        "category": "School of Agriculture",
        "keywords": ["agriculture", "syngenta", "agri internship", "b.sc agriculture", "placement", "success story", "corporate agri"]
    },

    # 6. Astra School of Business (MBA / BBA)
    "yYgB3h4wkug": {
        "category": "MBA & Business",
        "keywords": ["mba", "business school", "astra", "management", "future in business", "placements", "curriculum", "case study"]
    },
    "zAsyTVWNa0w": {
        "category": "MBA & Business",
        "keywords": ["astra school of business", "business", "bba", "mba", "entrepreneurship", "management", "leadership"]
    },
    "9tMJ-71k0zI": {
        "category": "MBA & Business",
        "keywords": ["astra school of business", "block", "inauguration", "infrastructure", "business building", "facilities"]
    },
    "wK0PGSNhyII": {
        "category": "MBA & Business",
        "keywords": ["ibap", "international business", "accelerated program", "global business", "bba", "study abroad"]
    },

    # 7. Startups & SRiX Incubator
    "A0NXVWcmLkQ": {
        "category": "Startups & Innovation (SRiX)",
        "keywords": ["srix", "startup", "startups", "incubator", "innovation hub", "entrepreneurship", "technology business incubator", "funding"]
    },
    "AcHDNyeVSlQ": {
        "category": "Startups & Innovation (SRiX)",
        "keywords": ["srix", "kotak", "kotak bizlabs", "partnership", "startup funding", "mentorship", "accelerator"]
    },
    "-9F-OFTDtuA": {
        "category": "Startups & Innovation (SRiX)",
        "keywords": ["project expo", "pragathi", "innovation", "prototypes", "engineering projects", "etv news", "exhibition"]
    },
    "SPvq-NGsL38": {
        "category": "Startups & Innovation (SRiX)",
        "keywords": ["yantra", "project expo", "tech expo", "hardware projects", "automation", "engineering innovations"]
    },

    # 8. Fests, Cultural Events & Sports
    "pSfz4l4vrMg": {
        "category": "Campus Life & Fests",
        "keywords": ["sparkrill", "sparkrill 2026", "ramp walk", "fashion", "college fest", "pro night", "celebration"]
    },
    "mF_4tWXedd4": {
        "category": "Campus Life & Fests",
        "keywords": ["navadhara", "bathukamma", "cultural fest", "traditional day", "dance", "celebrations", "traditional"]
    },
    "MWekBu0VLas": {
        "category": "Campus Life & Fests",
        "keywords": ["swagatam", "freshers", "freshers party", "orientation fest", "campus celebrations", "welcome party"]
    },
    "kFkaSToBX-A": {
        "category": "Campus Life & Fests",
        "keywords": ["ram miriyala", "sparkrill", "singer", "live concert", "pro night", "music", "performance"]
    },
    "sf2jDM21EN4": {
        "category": "Sports & Activities",
        "keywords": ["sports", "sports day", "athletics", "cricket", "tournament", "games", "ground", "medals"]
    },

    # 9. International Programs & Study Abroad
    "xfQVXz_bBA4": {
        "category": "International Programs",
        "keywords": ["international", "bangladesh", "international student", "global campus", "foreign students", "diversity"]
    },
    "VF5FgBIuWKI": {
        "category": "International Programs",
        "keywords": ["international", "myanmar", "b.tech cse", "foreign student", "experience", "diversity"]
    },
    "JZpvKru8dFw": {
        "category": "International Programs",
        "keywords": ["international", "zimbabwe", "africa", "international students", "living in india", "student experience"]
    },
    "QntEaaW5b34": {
        "category": "International Programs",
        "keywords": ["iep", "study abroad", "usa", "international engineering program", "degree abroad", "global transfer"]
    },

    # 10. Student Stories & Parent Reviews
    "1Xsz1ivgAAY": {
        "category": "Testimonials & Reviews",
        "keywords": ["parent review", "parent testimonial", "honest review", "parents speak", "why choose sru", "trust", "safety"]
    },
    "JHLCmt7K6KE": {
        "category": "Testimonials & Reviews",
        "keywords": ["student review", "student voice", "cse student", "why i chose sru", "experience", "honest opinion"]
    },
    "aeu_7SvIOus": {
        "category": "Testimonials & Reviews",
        "keywords": ["student journey", "bihar to sru", "b.tech cse", "career aspirations", "student review"]
    },
    "Q90RHVAi7fc": {
        "category": "Testimonials & Reviews",
        "keywords": ["student experience", "maharashtra to sru", "cse", "hostel and campus review", "outside telangana"]
    }
}

def main():
    entries = []
    
    # Read raw CSV to get exact title, URL, type
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vid_id = (row.get("Video ID") or "").strip()
            url = (row.get("URL") or "").strip()
            title = (row.get("Title") or "").strip()
            v_type = (row.get("Type") or "Video").strip()
            
            if vid_id in CURATED_CONFIG:
                cfg = CURATED_CONFIG[vid_id]
                thumbnail_url = f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
                entries.append({
                    "id": vid_id,
                    "platform": "youtube",
                    "type": "short" if v_type.lower() == "short" or "/shorts/" in url else "video",
                    "title": title,
                    "category": cfg["category"],
                    "url": url,
                    "thumbnail_url": thumbnail_url,
                    "channel_name": "SR University Official",
                    "channel_url": "https://www.youtube.com/@SRUniversity/videos",
                    "keywords": cfg["keywords"],
                })

    print(f"Curated {len(entries)} top-tier YouTube videos.")

    with open(output_path, "w", encoding="utf-8") as out:
        json.dump(entries, out, indent=2, ensure_ascii=False)

    print(f"Successfully saved {len(entries)} entries to {output_path}")

if __name__ == "__main__":
    main()
