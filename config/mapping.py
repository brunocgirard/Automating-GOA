cps_keywords = {
    # ... (PLC keywords) ...
    # ... (HMI keywords) ...
    
    # Control & Programming Specs - Other 
    "explosion resistant": "cps_ep_check",
    "explosion proof": "cps_ep_check",
    "swivel panel control": "cpp_2axis_check", # General keyword to trigger axis check
    # Removed: "three (x 3) colours status beacon light": "blt_red_check", 
    # Beacon light individual colors will be handled by LLM context + general description
    "audible alarm": "blt_audible_check", # Added for completeness
    "status beacon light": "blt_none_check", # A general keyword if specific colors aren't mentioned
    # ... (Rest of cps_keywords)
} 