import csv
import re
import sys

def parse_conditions(cond_str):
    if not cond_str:
        return ""
    
    # Replace CSV syntax with TahtLang syntax
    cond_str = cond_str.replace(" and ", ", ")
    cond_str = cond_str.replace("_keep", "") # Remove _keep suffix from flags in conditions
    
    # Convert ranges and operators if needed (TahtLang mostly compatible)
    # Special fix for ranges like 'age > 10' is fine. 
    
    parts = cond_str.split(", ")
    new_parts = []
    for part in parts:
        if part.startswith("!"):
            # !flag or !var
            if " " not in part and not any(op in part for op in [">", "<", "="]):
                new_parts.append(f"!flag:{part[1:]}")
            else:
                new_parts.append(part) # Assume counter logic is handled or complex
        elif any(op in part for op in [">", "<", "="]):
            # Counter check: military < 40 -> counter:military < 40
            # If it's already a known counter, prefix it.
            # Heuristic: if it looks like a variable comparison
            var_match = re.match(r"([a-zA-Z_]+)\s*([<>=]+)\s*(\d+)", part)
            if var_match:
                name, op, val = var_match.groups()
                new_parts.append(f"counter:{name} {op} {val}")
            else:
                new_parts.append(part)
        else:
            # Simple flag
            new_parts.append(f"flag:{part}")
            
    return ", ".join(new_parts)

def parse_effects(spiritual, military, demography, treasure, custom):
    cmds = []
    
    # Standard counters
    if spiritual: cmds.append(f"counter:spiritual {spiritual}")
    if military: cmds.append(f"counter:military {military}")
    if demography: cmds.append(f"counter:demography {demography}")
    if treasure: cmds.append(f"counter:treasure {treasure}")
    
    # Custom commands
    if custom:
        parts = custom.split(" and ")
        for part in parts:
            part = part.strip()
            if not part: continue
            
            # Remove _keep suffix from logic
            clean_part = part.replace("_keep", "")
            
            if clean_part.startswith("add_"):
                cmds.append(f"+flag:has_{clean_part[4:]}")
            elif clean_part.startswith("del_"):
                cmds.append(f"-flag:has_{clean_part[4:]}")
            elif clean_part.startswith(">>>>"):
                cmds.append(f"card:{clean_part[4:]}@3")
            elif clean_part.startswith(">>>"):
                cmds.append(f"card:{clean_part[3:]}@2")
            elif clean_part.startswith(">>"):
                cmds.append(f"card:{clean_part[2:]}@1")
            elif clean_part.startswith(">"):
                cmds.append(f"card:{clean_part[1:]}")
            elif clean_part.endswith("++"):
                cmds.append(f"counter:{clean_part[:-2]} 2") # Approx
            elif clean_part.endswith("+"):
                cmds.append(f"counter:{clean_part[:-1]} 1")
            elif clean_part.startswith("!"):
                cmds.append(f"-flag:{clean_part[1:]}")
            else:
                # Assume it's adding a flag if no other syntax matches
                # But wait, CSV has things like 'tower_keep' in custom which means ADD flag
                cmds.append(f"+flag:{clean_part}")

    return ", ".join(cmds)

def clean_text(text):
    if not text: return ""
    return text.replace('"', '\"').strip()

def convert_row(row):
    # CSV Columns (0-based index from decoded csv which has header) 
    # 0:thematic; 1:card; 2:id; 3:bearer; 4:conditions; 5:lockturn; 6:weight; 
    # 7:question; 8:yes_label; 9:yes_answer; 10:yes_sp; 11:yes_mil; 12:yes_dem; 13:yes_tr; 14:yes_custom;
    # 15:no_label; 16:no_answer; 17:no_sp; 18:no_mil; 19:no_dem; 20:no_tr; 21:no_custom; 22:vide
    
    try:
        card_id = row[1].strip()
        numeric_id = row[2].strip()
        bearer_raw = row[3].strip()
        conditions = row[4].strip()
        lockturn = row[5].strip()
        weight = row[6].strip()
        question = row[7].strip()
        
        # Yes effects
        yes_label = row[8].strip()
        yes_custom = row[14].strip()
        yes_effects = parse_effects(row[10], row[11], row[12], row[13], yes_custom)
        
        # No effects
        no_label = row[15].strip()
        no_custom = row[21].strip()
        no_effects = parse_effects(row[17], row[18], row[19], row[20], no_custom)
        
        # Card ID logic
        is_ring = False
        # Fix: If card_id is empty OR just "_", generate a name
        if not card_id or card_id == "_":
            # Clean thematic name (remove spaces, etc)
            theme = row[0].strip().replace(" ", "_").lower()
            if not theme: theme = "card"
            card_id = f"{theme}_{numeric_id}"
            is_ring = True # Usually these are ring/event cards if they have no name
        
        if card_id.startswith("_"):
            is_ring = True
        
        if not weight:
            is_ring = True
            
        # Unique ID for TahtLang (handling duplicates is hard here without global context, 
        # but we can append numeric ID to generic names if needed, or just trust the porter handles it later. 
        # For now, let's use the provided ID. If it duplicates, we might need manual fix, 
        # but let's append numeric ID if it looks very generic) 
        
        final_id = card_id
        tags = []
        if is_ring:
            tags.append("ring")
            
        id_str = f"card:{final_id}"
        if tags:
            id_str += ", " + ", ".join(tags)

        # Bearer logic
        bearer_parts = bearer_raw.split(">")
        bearer_name = bearer_parts[0]
        variant = ""
        if len(bearer_parts) > 1:
            variant = f" (variant:{bearer_parts[1]})"
            
        # Output TahtLang format
        print(f"Card {numeric_id} ({id_str})")
        print(f"\t# Original ID: {numeric_id}")
        print(f"\tbearer: character:{bearer_name}{variant}")
        
        if conditions:
            print(f"\trequire: {parse_conditions(conditions)}")
            
        if weight and not is_ring:
             print(f"\tweight: {weight}")
        
        if lockturn:
            # Map specific lockturn values
            if lockturn == "del" or lockturn == "reign":
                print(f"\tlockturn: dispose")
            elif lockturn == "once":
                print(f"\tlockturn: once") # TahtLang supports once? Or map to dispose? Using dispose for now or literal if supported.
                # Spec says 'lockturn: dispose' is common.
            else:
                print(f"\tlockturn: {lockturn}")
                
        print(f"\t> {clean_text(question)}")
        
        print(f"\t* {clean_text(yes_label) or 'Yes'}: {yes_effects}")
        print(f"\t* {clean_text(no_label) or 'No'}: {no_effects}")
        print("") # Empty line

    except Exception as e:
        print(f"# ERROR converting row {row[2]}: {e}")

def main():
    csv_path = 'archive/reigns_data/cards_decoded.csv'
    start_id = 411
    end_id = 887
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        next(reader) # Skip header
        
        for row in reader:
            try:
                current_id = int(row[2])
                if start_id <= current_id <= end_id:
                    convert_row(row)
            except ValueError:
                continue

if __name__ == "__main__":
    main()
