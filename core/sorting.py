import datetime

def parse_timestamp(ts_str):
    """Converts unix timestamp string to datetime object."""
    try:
        return datetime.datetime.fromtimestamp(int(ts_str))
    except:
        return datetime.datetime.now()

def should_process(filename, timestamp, settings):
    """
    Decides if a file should be processed based on Phase 2 filters.
    timestamp: datetime object
    """
    
    # 1. Letter Filter
    if settings.get("filter_enable_letter", False):
        start_char = settings.get("filter_letter_start", "A").upper()
        end_char = settings.get("filter_letter_end", "Z").upper()
        
        first_char = filename[0].upper()
        
        # Simple lexicographical check
        if not (start_char <= first_char <= end_char):
            return False, f"Name '{filename}' outside range {start_char}-{end_char}"

    # 2. Date Filter
    if settings.get("filter_enable_date", False):
        try:
            s_str = settings.get("filter_date_start", "1900-01-01")
            e_str = settings.get("filter_date_end", "2100-01-01")
            
            s_date = datetime.datetime.strptime(s_str, "%Y-%m-%d")
            e_date = datetime.datetime.strptime(e_str, "%Y-%m-%d")
            # Set end date to end of that day
            e_date = e_date.replace(hour=23, minute=59, second=59)

            if not (s_date <= timestamp <= e_date):
                return False, f"Date {timestamp.date()} outside {s_str} to {e_str}"
                
        except ValueError:
            pass # Invalid config, ignore filter

    return True, "OK"