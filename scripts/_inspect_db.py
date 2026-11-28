from src.database.connection import get_session, is_postgres
from sqlalchemy import text
s = get_session()
print('is_postgres:', is_postgres())
for tbl in ['companies', 'stock_prices', 'market_indices', 'technical_indicators']:
    try:
        res = s.execute(text(f'SELECT count(*) FROM {tbl}')).fetchone()
        print(f'{tbl} row count:', res[0])
    except Exception as e:
        print(f'{tbl} error:', e)
s.close()
