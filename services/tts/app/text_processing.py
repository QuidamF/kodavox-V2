import re

# Configurable limits
TARGET_LENGTH = 85   # Ideal chunk size (soft limit)
MAX_LENGTH = 140     # Absolute maximum (hard limit)

def clean_text(text: str) -> str:
    """
    Normalizes text to remove problematic characters for XTTS.
    Replaces dialogue dashes with commas for better prosody.
    """
    print(f"--- Raw text input: '{text[:50]}...' (Length: {len(text)}) ---")
    
    # Replace em-dashes, en-dashes, and parentheses with spaces
    # Commas can sometimes cause weird pauses or conflicts like ",."
    text = text.replace("–", " ").replace("—", " ").replace("(", " ").replace(")", " ")
    
    # Replace non-breaking spaces and other weird whitespace
    text = text.replace("\u00A0", " ").replace("\r", " ").replace("\n", " ")
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove spaces before punctuation (XTTS doesn't like "word .")
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    
    cleaned = text.strip()
    print(f"--- Cleaned text: '{cleaned[:50]}...' (Length: {len(cleaned)}) ---")
    return cleaned

def split_into_sentences(text: str):
    """
    Splits text into chunks using a smart lookahead strategy.
    Prioritizes splitting at sentence terminators -> clauses -> spaces,
    keeping chunks as close to TARGET_LENGTH as possible without exceeding MAX_LENGTH.
    """
    text = clean_text(text)
    chunks = []
    
    while len(text) > MAX_LENGTH:
        # 1. Try to split at a sentence terminator (., !, ?) within ideal range
        # Look for the last terminator before MAX_LENGTH
        split_point = -1
        
        # Priority 1: Sentence Enders in the "Safe Zone" (TARGET to MAX)
        match = re.search(r'[.!?]\s+(?=[A-Z])', text[:MAX_LENGTH])
        if match:
             # Find the LAST match to maximize chunk size
             all_matches = list(re.finditer(r'[.!?]\s+', text[:MAX_LENGTH]))
             if all_matches:
                 split_point = all_matches[-1].end()
        
        # Priority 2: Clause Enders (comma, semicolon)
        if split_point == -1:
            all_matches = list(re.finditer(r'[,;:]\s+', text[:MAX_LENGTH]))
            # Prefer splitting closer to TARGET_LENGTH
            best_match = None
            for m in all_matches:
                if m.end() > 20: # Avoid very short starts
                    best_match = m
            if best_match:
                split_point = best_match.end()

        # Priority 3: Spaces (User's request: nearest space to target)
        if split_point == -1:
            # Look for space around TARGET_LENGTH
            # Search backwards from MAX_LENGTH
            last_space = text.rfind(' ', 0, MAX_LENGTH)
            if last_space > 20:
                split_point = last_space + 1 # Include space in first chunk
        
        # Fallback: Hard split if no spaces found (giant word)
        if split_point == -1:
            split_point = MAX_LENGTH

        # Cut the chunk
        chunk = text[:split_point].strip()
        if chunk:
            chunks.append(chunk)
        
        # Advance text
        text = text[split_point:].strip()
    
    # Add remaining text
    if text:
        chunks.append(text)

    print("--- Final Segments ---")
    for i, s in enumerate(chunks):
        print(f"Segment {i+1}: '[{s}]' (Len: {len(s)})")
    print("----------------------")
    
    return chunks
