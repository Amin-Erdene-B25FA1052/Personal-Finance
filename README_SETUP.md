# Миний санхүү — MacBook дээр ажиллуулах

## 1. VS Code Terminal

```bash
cd ~/Downloads/finance-tool-kit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

## 2. PostgreSQL 14+ суулгах

Mac дээр [Postgres.app](https://postgresapp.com/) суулгаад нээж Start дарна. `psql` командыг ашиглахын тулд Postgres.app-ийн зааврын дагуу PATH тохируулна. Өөр сонголт: Homebrew PostgreSQL.

Terminal дээр:

```bash
createdb finance_tool
psql -d finance_tool -f schema.sql
```

Хэрэв `createdb: command not found` гарвал PostgreSQL-ийн CLI PATH-д байхгүй байна. Postgres.app-ийн CLI тохиргоог хийнэ.

Хэрэв PostgreSQL хэрэглэгч/нууц үг шаардаж байвал URL-аа локал shell-д тохируулна:

```bash
export DATABASE_URL='postgresql://YOUR_USER:YOUR_PASSWORD@localhost:5432/finance_tool'
```

`DATABASE_URL`-ийг GitHub-д commit хийж болохгүй. Локал password-оо бусдад битгий илгээ.

## 3. Апп нээх

```bash
source .venv/bin/activate
python app.py
```

Browser дээр `http://127.0.0.1:5000` нээнэ. Stop: `Control + C`.

## 4. Жишээ файл

`fixtures/capitron_sample_anonymised.xlsx` файлыг upload хийж туршина. Merchant ангиллыг “Худалдааны газрууд” хэсэгт онооно. Нэг гүйлгээний ангиллыг үндсэн дэлгэц дээр өөрчилнө.

## Анхаарах зүйлс

- Энэ хувилбар нь **зөвхөн Capitron банкны өгөгдсөн загвартай** Excel хуулгыг дэмжинэ. Бусад банкны адаптер нэмэх шаардлагатай.
- Одоогийн апп зөвхөн **127.0.0.1** дээр ажиллана, нэвтрэх системгүй тул интернэтэд нээж болохгүй.
- Давхардлыг банкны хуулгын хязгаарлалттай natural key болон файлын SHA256-аар шалгана; ижил цаг, дүн, үлдэгдэлтэй хоёр тусдаа гүйлгээний онцгой тохиолдолд нягтлах шаардлагатай.
- Тестүүд 16/16 амжилттай ажилласан (Python орчинд). PostgreSQL-тай интеграц тестийг MacBook дээр ажиллуулж шалгах хэрэгтэй.
- Банкны бодит хуулгыг GitHub-д commit хийж болохгүй. `.gitignore`-д Excel файлуудыг хаасан.
- Өөрийн компьютер дээр PostgreSQL өгөгдлийн сангийн нөөцлөлтийг тогтмол хийнэ.
