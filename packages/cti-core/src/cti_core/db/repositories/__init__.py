"""Repository -- pintu masuk baca/tulis satu-satunya buat tiap agregat.

Pola tiap modul: satu class sync (`XRepo`, dipakai Celery/CLI/scraper) dan
satu class async (`AsyncXRepo`, dipakai FastAPI). Query dan business rule
sama persis, beda cuma `await` -- lihat plan §5.2. Jangan query model
langsung dari luar repository (scraper, task, endpoint), supaya aturan
kayak "overrides gak boleh ketimpa" (lihat ArticleRepo) gak bisa dilewatin.
"""
