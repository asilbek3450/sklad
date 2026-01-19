
import os
import django
import random
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from shop.models import Category, Product, CustomUser

def populate():
    print("Populating database...")

    # 1. Create Users
    if not CustomUser.objects.filter(username='admin').exists():
        CustomUser.objects.create_superuser('admin', 'admin@example.com', 'password', role='admin', fullname='Super Admin', telegram_id=123456789)
        print("Created superuser 'admin'")

    if not CustomUser.objects.filter(username='kassir').exists():
        CustomUser.objects.create_user('kassir', 'kassir@example.com', 'password', role='kassir', fullname='Kassir 1', telegram_id=987654321)
        print("Created user 'kassir'")
        
    # 2. Categories
    categories_list = [
        "Ichimliklar", "Sut mahsulotlari", "Non mahsulotlari", "Mevalar", "Sabzavotlar", 
        "Go'sht mahsulotlari", "Shirinliklar", "Yuvish vositalari", "Gigiena", "Boshqa"
    ]
    
    cats = []
    for cat_name in categories_list:
        c, created = Category.objects.get_or_create(nomi=cat_name)
        cats.append(c)
        if created:
            print(f"Created category: {cat_name}")
            
    # 3. Products
    prefixes = ["Super", "Extra", "Tabiiy", "Mazali", "Yangi", "Arzon"]
    suffixes = ["Plus", "Gold", "Premium", "XXL", "1kg", "0.5l"]
    
    product_bases = {
        "Ichimliklar": ["Cola", "Fanta", "Sprite", "Suv", "Sharbat", "Choy", "Qahva", "Energetik", "Limonad", "Ayran"],
        "Sut mahsulotlari": ["Sut", "Qatiq", "Qaymoq", "Tvorog", "Sariyog'", "Yogurt", "Pishloq", "Brynza", "Sgushchenka", "Kefir"],
        "Non mahsulotlari": ["Non", "Baton", "Buxanka", "Patir", "Losh", "Pechenye", "Vafli", "Keks", "Rulet", "Tort"],
        "Mevalar": ["Olma", "Armut", "Uzum", "Banan", "Apelsin", "Mandarin", "Kivi", "Anor", "Shaftoli", "O'rik"],
        "Sabzavotlar": ["Kartoshka", "Piyoz", "Sabzi", "Karam", "Pomidor", "Bodring", "Baqlajon", "Qalampir", "Sarimsoq", "Oshqovoq"],
        "Go'sht mahsulotlari": ["Mol go'shti", "Qo'y go'shti", "Tovuq", "Kolbasa", "Sosiska", "Qiyma", "Jigar", "Tuxum", "Baliq", "File"],
        "Shirinliklar": ["Shokolad", "Konfet", "Marmelad", "Zefir", "Holva", "Navvot", "Chak-chak", "Snickers", "Mars", "Twix"],
        "Yuvish vositalari": ["Kukun", "Sovun", "Shampun", "Gelya", "Vanish", "Domestos", "Fairy", "Ariel", "Persil", "Lenor"],
        "Gigiena": ["Tish pastasi", "Cho'tka", "Salfetka", "Qog'oz", "Pampers", "Sovun", "Dezodorant", "Britva", "Krem", "Niqob"],
        "Boshqa": ["Batareyka", "Gugurt", "Zajigalka", "Qalam", "Daftar", "Ruchka", "Skotch", "Yelim", "Paket", "Lampa"]
    }

    count = 0
    for cat in cats:
        bases = product_bases.get(cat.nomi, ["Mahsulot"])
        for i in range(10): # Ensure at least 10 products per category
            
            # Use specific base names if available, reusing them with variations if needed
            base_name = bases[i % len(bases)]
            
            name = f"{random.choice(prefixes)} {base_name}"
            # Add suffix randomly to vary names closer to real life
            if random.random() > 0.5:
                name += f" {random.choice(suffixes)}"

            # Price between 5000 and 150000 som
            price = Decimal(random.randint(5, 150)) * 1000 
            
            Product.objects.create(
                nomi=name,
                kategoriya=cat,
                narx=price,
                barcode=str(random.randint(10000000, 99999999)),
                minimal_qoldiq=random.choice([5, 10, 15, 20])
            )
            count += 1
            
    print(f"Success! Total products created: {count}")

if __name__ == '__main__':
    populate()
