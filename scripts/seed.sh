#!/bin/bash
# 資料初始化腳本
echo "Seeding database..."

python -c "
from config.database import DATABASE_URL
print(f'Database: {DATABASE_URL}')
# 在此加入初始資料邏輯
print('Seed complete.')
"
