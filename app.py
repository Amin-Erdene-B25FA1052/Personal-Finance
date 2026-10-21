"""Local-only personal finance web app. Run: python app.py"""
import hashlib
import os
import tempfile
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg
from psycopg.rows import dict_row
from werkzeug.utils import secure_filename
from finance_tool.banks.capitron import CapitronAdapter
from finance_tool.classify import classify_line, owner_key
from finance_tool.models import StatementError

BASE=Path(__file__).resolve().parent
app=Flask(__name__)
app.secret_key=os.environ.get('FLASK_SECRET_KEY','local-only-development-key')
app.config['MAX_CONTENT_LENGTH']=12*1024*1024
URL=os.environ.get('DATABASE_URL','postgresql://localhost/finance_tool')

def db():return psycopg.connect(URL,row_factory=dict_row)

def category_list(conn):
    return conn.execute('SELECT id,name,kind FROM categories ORDER BY sort_order,name').fetchall()

@app.template_filter('mnt')
def mnt(v):return f'{Decimal(v or 0):,.0f} ₮'

@app.route('/')
def home():
    try:
        with db() as conn:
            summary=conn.execute('''SELECT COALESCE(sum(t.credit) FILTER (WHERE c.kind='income'),0) income, COALESCE(sum(t.debit) FILTER (WHERE c.kind='expense'),0) expense, count(*) total, count(*) FILTER (WHERE t.category_id IS NULL) pending FROM transactions t LEFT JOIN categories c ON c.id=t.category_id''').fetchone()
            transactions=conn.execute('''SELECT t.*,c.name category,m.display_name merchant FROM transactions t LEFT JOIN categories c ON c.id=t.category_id LEFT JOIN merchants m ON m.id=t.merchant_id ORDER BY t.posted_at DESC,t.id DESC LIMIT 250''').fetchall()
            cats=category_list(conn)
            groups=conn.execute('''SELECT c.name,c.kind,COALESCE(sum(CASE WHEN c.kind='income' THEN t.credit ELSE t.debit END),0) amount FROM transactions t JOIN categories c ON c.id=t.category_id WHERE c.kind!='transfer' GROUP BY c.name,c.kind ORDER BY amount DESC''').fetchall()
        return render_template('index.html',summary=summary,transactions=transactions,cats=cats,groups=groups)
    except psycopg.Error as e:
        return f'<h2>PostgreSQL холбогдсонгүй</h2><p>README_SETUP.md зааврыг шалгаарай.</p><pre>{str(e)}</pre>',503

@app.get('/dashboard')
def dashboard():
    # Read-only financial dashboard; excludes transfers and unclassified rows.
    from datetime import date, timedelta
    from calendar import monthrange
    today=date.today()
    end_raw=request.args.get('end','').strip()
    start_raw=request.args.get('start','').strip()
    try:
        end=date.fromisoformat(end_raw) if end_raw else today
        start=date.fromisoformat(start_raw) if start_raw else (end.replace(day=1)-timedelta(days=1)).replace(day=1)
        if start>end: raise ValueError('start after end')
        if (end-start).days>3660: raise ValueError('range too large')
    except ValueError:
        flash('Огнооны интервал буруу байна.');return redirect(url_for('dashboard'))
    account_raw=request.args.get('account','').strip()
    try: account_id=int(account_raw) if account_raw else None
    except ValueError:
        flash('Дансны сонголт буруу байна.');return redirect(url_for('dashboard'))
    try:
        with db() as conn:
            accounts=conn.execute('SELECT id,account_no,holder_name FROM accounts ORDER BY account_no').fetchall()
            if account_id is not None and not any(a['id']==account_id for a in accounts):
                flash('Сонгосон данс олдсонгүй.');return redirect(url_for('dashboard'))
            params=(start,end,account_id,account_id)
            where='t.txn_date BETWEEN %s AND %s AND (%s::bigint IS NULL OR t.account_id=%s)'
            summary=conn.execute(f'''SELECT count(*) total,
                count(*) FILTER (WHERE t.category_id IS NULL) pending,
                COALESCE(sum(t.credit) FILTER (WHERE c.kind='income'),0) income,
                COALESCE(sum(t.debit) FILTER (WHERE c.kind='expense'),0) expense,
                COALESCE(sum(t.credit) FILTER (WHERE t.category_id IS NULL),0) uncategorized_credit,
                COALESCE(sum(t.debit) FILTER (WHERE t.category_id IS NULL),0) uncategorized_debit
                FROM transactions t LEFT JOIN categories c ON c.id=t.category_id WHERE {where}''',params).fetchone()
            
            monthly=conn.execute(f'''SELECT
                to_char(date_trunc('month', t.txn_date), 'YYYY-MM') AS txn_month,
                COALESCE(sum(t.credit) FILTER (WHERE c.kind='income'),0) AS income,
                COALESCE(sum(t.debit) FILTER (WHERE c.kind='expense'),0) AS expense
                FROM transactions t
                LEFT JOIN categories c ON c.id=t.category_id
                WHERE {where}
                GROUP BY 1
                ORDER BY 1''', params).fetchall()
            categories=conn.execute(f'''SELECT c.name,COALESCE(sum(t.debit),0) amount
                FROM transactions t JOIN categories c ON c.id=t.category_id
                WHERE {where} AND c.kind='expense' GROUP BY c.id,c.name ORDER BY amount DESC''',params).fetchall()
            merchants=conn.execute(f'''SELECT COALESCE(m.display_name,NULLIF(t.counterparty_name,''),'Тодорхойгүй') name,
                COALESCE(sum(t.debit),0) amount,count(*) transactions
                FROM transactions t LEFT JOIN merchants m ON m.id=t.merchant_id
                LEFT JOIN categories c ON c.id=t.category_id
                WHERE {where} AND c.kind='expense' AND t.debit>0
                GROUP BY 1 ORDER BY amount DESC LIMIT 10''',params).fetchall()
            recent=conn.execute(f'''SELECT t.txn_date,t.description,t.debit,t.credit,c.name category
                FROM transactions t LEFT JOIN categories c ON c.id=t.category_id
                WHERE {where} ORDER BY t.txn_date DESC,t.id DESC LIMIT 12''',params).fetchall()
        
            chart_months = [
                {
                    'month': r['txn_month'],
                    'income': float(r['income']),
                    'expense': float(r['expense'])
                }
                for r in monthly
            ]

        chart_categories=[{'name':r['name'],'amount':float(r['amount'])} for r in categories]
        chart_merchants=[{'name':r['name'],'amount':float(r['amount'])} for r in merchants]
        return render_template('dashboard.html',summary=summary,monthly=chart_months,categories=chart_categories,
            merchants=chart_merchants,recent=recent,accounts=accounts,account_id=account_id,
            start=start.isoformat(),end=end.isoformat(),net=summary['income']-summary['expense'])
    except psycopg.Error as e:
        return f'<h2>PostgreSQL холбогдсонгүй</h2><p>README_SETUP.md зааврыг шалгаарай.</p><pre>{str(e)}</pre>',503

@app.post('/upload')
def upload():
    f=request.files.get('statement')
    if not f or not f.filename.lower().endswith('.xlsx'):
        flash('Зөвхөн .xlsx файл оруулна.');return redirect(url_for('home'))
    content=f.read();digest=hashlib.sha256(content).hexdigest()
    path=None
    try:
        with tempfile.NamedTemporaryFile(suffix='.xlsx',delete=False) as tmp:
            tmp.write(content);path=tmp.name
        st=CapitronAdapter().parse(path)
        with db() as conn:
            if conn.execute('SELECT 1 FROM import_batches WHERE file_sha256=%s',(digest,)).fetchone():
                flash('Энэ файлыг өмнө нь оруулсан байна.');return redirect(url_for('home'))
            account=conn.execute('''INSERT INTO accounts(bank_code,account_no,holder_name) VALUES(%s,%s,%s) ON CONFLICT(account_no) DO UPDATE SET holder_name=excluded.holder_name RETURNING id''',(st.bank_code,st.account_no,st.holder_name)).fetchone()['id']
            batch=conn.execute('''INSERT INTO import_batches(account_id,filename,file_sha256,period_from,period_to,opening_balance,closing_balance,rows_in_file,rows_new,rows_skipped) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,0,0) RETURNING id''',(account,secure_filename(f.filename),digest,st.period_from,st.period_to,st.opening_balance,st.closing_balance,len(st.transactions))).fetchone()['id']
            new=0
            for t in st.transactions:
                result=classify_line(t.description,t.counterparty_account,owner_key(st.holder_name))
                cat=None;merchant=None;source=result.source
                if result.category_name:
                    r=conn.execute('SELECT id FROM categories WHERE name=%s',(result.category_name,)).fetchone();cat=r['id'] if r else None
                if result.merchant_key:
                    r=conn.execute('''INSERT INTO merchants(merchant_key,display_name) VALUES(%s,%s) ON CONFLICT(merchant_key) DO UPDATE SET display_name=excluded.display_name RETURNING id,category_id''',(result.merchant_key,result.merchant_name)).fetchone()
                    merchant=r['id']
                    if r['category_id'] is not None:cat=r['category_id'];source='merchant'
                row=conn.execute('''INSERT INTO transactions(account_id,batch_id,txn_date,posted_at,debit,credit,balance_after,description,counterparty_account,counterparty_name,merchant_id,category_id,category_source) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT ON CONSTRAINT transactions_natural_key DO NOTHING RETURNING id''',(account,batch,t.txn_date,t.posted_at,t.debit,t.credit,t.balance_after,t.description,t.counterparty_account,t.counterparty_name,merchant,cat,source)).fetchone()
                if row:new+=1
            conn.execute('UPDATE import_batches SET rows_new=%s,rows_skipped=%s WHERE id=%s',(new,len(st.transactions)-new,batch))
        flash(f'{len(st.transactions)} мөр уншлаа. {new} шинэ гүйлгээ хадгаллаа.')
    except (StatementError,psycopg.Error,ValueError) as e:flash(f'Импортын алдаа: {e}')
    finally:
        if path:os.unlink(path)
    return redirect(url_for('home'))

@app.route('/merchants',methods=['GET','POST'])
def merchants():
    with db() as conn:
        if request.method=='POST':
            mid=int(request.form['merchant_id']);cid=request.form.get('category_id') or None
            conn.execute('UPDATE merchants SET category_id=%s WHERE id=%s',(cid,mid))
            conn.execute("UPDATE transactions SET category_id=%s,category_source=CASE WHEN %s::bigint IS NULL THEN 'none' ELSE 'merchant' END WHERE merchant_id=%s AND category_source NOT IN ('manual','rule','own')",(cid,cid,mid))
            flash('Худалдааны газрын ангиллыг хадгаллаа.')
            return redirect(url_for('merchants'))
        rows=conn.execute('''SELECT m.*,count(t.id) n FROM merchants m LEFT JOIN transactions t ON t.merchant_id=m.id GROUP BY m.id ORDER BY m.category_id NULLS FIRST,m.display_name''').fetchall()
        cats=category_list(conn)
    return render_template('merchants.html',merchants=rows,cats=cats)

@app.post('/transaction/<int:tid>')
def edit_transaction(tid):
    cid=request.form.get('category_id') or None
    with db() as conn:
        conn.execute("UPDATE transactions SET category_id=%s,category_source='manual' WHERE id=%s",(cid,tid))
    flash('Гүйлгээний ангиллыг өөрчиллөө.')
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=False, port=5001)
