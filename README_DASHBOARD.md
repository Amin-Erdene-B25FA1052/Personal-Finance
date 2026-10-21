# Dashboard нэмэлт

1. PostgreSQL серверээ асаана. Өмнөх өгөгдлийн сангаа хэвээр ашиглана; schema migration шаардлагагүй.
2. VS Code-д энэ хавтсыг нээнэ.
3. Terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

4. Chrome дээр `http://127.0.0.1:5000/dashboard` нээнэ.
5. Dashboard холбоос үндсэн цэсэнд нэмэгдсэн. Огноо, дансаар шүүж болно.

Анхаарах: Орлого/зарлага зөвхөн ангилсан мөрөөр тооцогдоно. `transfer` болон ангилаагүй гүйлгээг хасна. Цэвэр мөнгөн урсгал нь бодит банкны дансны үлдэгдэл биш. Chart.js график интернэтээс CDN-ээр ачаалагдана. Бодит банкны хуулга болон нууц үгийг GitHub-д оруулж болохгүй.
