from app.services.profile_service import extract_student_profile

tests = [
    "i got 85% in 12th pcm",
    "my 12th marks are 72",
    "my 12th marks are 72 percent",
    "scored 60 in inter",
    "marks 55",
    "78 marks in 12th",
    "i have 91 in boards",
    "pcm 88",
    "got 45",
    "my score is 80",
    "i scored 93",
    "85 in intermediate",
    "my boards percentage is 67",
    "class 12 score 74",
    "12th result 82%",
    "got 55 marks",
    "12 marks 79",
]
print("Score extraction test results:")
misses = []
for t in tests:
    p = extract_student_profile([{"role": "user", "content": t}])
    status = "OK  " if p["has_score"] else "MISS"
    print(f"  [{status}] \"{t}\" -> score_pct={p['score_pct']}")
    if not p["has_score"]:
        misses.append(t)

print(f"\n{len(misses)} misses out of {len(tests)}")
for m in misses:
    print(f"  MISS: {m}")
