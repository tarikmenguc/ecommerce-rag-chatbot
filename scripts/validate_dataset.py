import json

with open("data/synthetic_train_ollama.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total items: {len(lines)}")

# Check first item structure
item = json.loads(lines[0])
print(f"Keys: {list(item.keys())}")
print(f"Message count: {len(item['messages'])}")
for m in item["messages"]:
    print(f"  role: {m['role']}, content_len: {len(m['content'])} chars")

# Check last item
last_item = json.loads(lines[-1])
print(f"\nLast item roles:")
for m in last_item["messages"]:
    print(f"  role: {m['role']}, content_len: {len(m['content'])} chars")

# Validate all lines
bad = 0
short_assistant = 0
for i, line in enumerate(lines):
    try:
        d = json.loads(line)
        msgs = d.get("messages", [])
        roles = [m["role"] for m in msgs]
        if "user" not in roles or "assistant" not in roles:
            bad += 1
            print(f"  Missing role at line {i}")
        # Check if assistant response is suspiciously short
        for m in msgs:
            if m["role"] == "assistant" and len(m["content"].split()) < 30:
                short_assistant += 1
    except Exception as e:
        bad += 1
        print(f"  Error at line {i}: {e}")

print(f"\nBad/malformed lines: {bad}")
print(f"Short assistant responses (<30 words): {short_assistant}")

# Show a random sample from the middle
import random
random.seed(42)
sample_idx = random.choice(range(len(lines) // 3, 2 * len(lines) // 3))
sample = json.loads(lines[sample_idx])
user_msg = next(m["content"] for m in sample["messages"] if m["role"] == "user")
asst_msg = next(m["content"] for m in sample["messages"] if m["role"] == "assistant")
print(f"\n--- RANDOM SAMPLE (index {sample_idx}) ---")
print(f"[USER]:\n{user_msg[:200]}")
print(f"\n[ASSISTANT]:\n{asst_msg[:500]}")
