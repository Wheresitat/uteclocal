# U-tec Local Gateway – Home Assistant Integration

Custom integration to expose U-tec locks via a local gateway.

## Install via HACS
1. Add custom repo: https://github.com/Wheresitat/uteclocal
2. Category: Integration
3. Install
4. Restart HA
5. Add Integration → 'U-tec Local Gateway'
6. Enter host of your gateway (e.g., http://batdock:8000)

Your locks will appear as `lock.*` entities if `/api/devices` returns them.
