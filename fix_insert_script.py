import re

with open("insert_data_guide.py", "r", encoding="utf-8") as f:
    text = f.read()

if "from typing import Any, cast" not in text:
    text = text.replace("import sys\n", "import sys\nfrom typing import Any, cast\n")

# Find each try block that has result = self.supabase.table(...).insert(...).execute()
# and replace the usages of result.data with data, where data is casted.

pattern = re.compile(r'(result = self\.supabase\.table\([^)]+\)\.insert\([^)]+\)\.execute\(\))(\s*)(.*?)\n\s*except Exception', re.DOTALL)

def replacer(match):
    insert_stmt = match.group(1)
    spaces = match.group(2)
    inner_block = match.group(3)
    
    # Prefix the block with our data variable
    # Match the indentation of the try block content
    indent = "\n" + spaces.strip("\n")
    
    new_inner_block = inner_block.replace("result.data", "data")
    
    return f"{insert_stmt}{indent}data = cast(list[dict[str, Any]], result.data or []){indent}{new_inner_block}\n        except Exception"

text = pattern.sub(replacer, text)

# Just in case some result.data are handled differently or to fix return result.data which became return data
text = text.replace("return data", "return result.data")

with open("insert_data_guide.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Finished updates.")
