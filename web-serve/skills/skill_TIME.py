import sys
import json
from datetime import datetime
import pytz

def main():
    try:
        argv = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    except:
        argv = {}
    
    timezone = argv.get('timezone', 'Asia/Shanghai')
    try:
        tz = pytz.timezone(timezone)
    except:
        tz = pytz.timezone('Asia/Shanghai')
    
    now = datetime.now(tz)
    print(now.strftime('%Y-%m-%d %H:%M:%S %Z'))

if __name__ == '__main__':
    main()