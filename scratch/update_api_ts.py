path = "frontend/src/api.ts"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target = """  id?: string;
  saved_to_history?: boolean;
};"""

replacement = """  id?: string;
  saved_to_history?: boolean;
  grass_age?: string;
  age_ai_guidance?: string | null;
};"""

content = content.replace(target, replacement, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated frontend/src/api.ts successfully.")

