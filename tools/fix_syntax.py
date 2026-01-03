import re
import sys

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Regex to find card usage with > prefix
    # Pattern: card: (>+) (optional identifier) (optional @delay)
    # But wait, the grep showed 'card:>>battleviking@3'.
    # Regex: card:(>+)([a-zA-Z0-9_]*)
    
    def replacer(match):
        arrows = match.group(1)
        ident = match.group(2)
        
        # We just remove the arrows. 
        # The delay might be already in the string after this match?
        # No, let's look at the context.
        # If the text is "card:>>battleviking@3", match is "card:>>battleviking".
        # The result will be "card:battleviking".
        # So "card:battleviking@3". Correct.
        
        # If the text is "card:>>>>>>@3", match is "card:>>>>>>".
        # The result will be "card:".
        # So "card:@3". This is invalid.
        
        if not ident:
            return "card:_next_card"
        
        return f"card:{ident}"

    new_content = re.sub(r'card:(>+)([a-zA-Z0-9_]*)', replacer, content)
    
    with open(filepath, 'w') as f:
        f.write(new_content)

if __name__ == "__main__":
    fix_file(sys.argv[1])
