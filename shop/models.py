from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _


class CustomUser(AbstractUser):
    """Foydalanuvchi modeli"""
    ROLE_CHOICES = [
        ('admin', _('Admin')),
        ('kassir', _('Kassir')),
    ]
    
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True, verbose_name=_("Telegram ID"))
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='kassir', verbose_name=_("Rol"))
    fullname = models.CharField(max_length=255, verbose_name=_("To'liq ism"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Yaratilgan sana"))
    
    class Meta:
        verbose_name = _("Foydalanuvchi")
        verbose_name_plural = _("Foydalanuvchilar")
    
    def __str__(self):
        return f"{self.fullname} ({self.get_role_display()})"



class Category(models.Model):
    """Kategoriya modeli"""
    nomi = models.CharField(max_length=100, verbose_name=_("Kategoriya nomi"))
    
    class Meta:
        verbose_name = _("Kategoriya")
        verbose_name_plural = _("Kategoriyalar")
        
    def __str__(self):
        return self.nomi


class Product(models.Model):
    """Mahsulot modeli"""
    nomi = models.CharField(max_length=255, verbose_name=_("Nomi"))
    kategoriya = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name=_("Kategoriya"))
    narx = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Narx"))
    barcode = models.CharField(max_length=100, unique=True, null=True, blank=True, verbose_name=_("Barcode"))
    minimal_qoldiq = models.IntegerField(default=10, verbose_name=_("Minimal qoldiq"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Yaratilgan sana"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("O'zgartirilgan sana"))
    
    class Meta:
        verbose_name = _("Mahsulot")
        verbose_name_plural = _("Mahsulotlar")
        ordering = ['-created_at']
    
    def __str__(self):
        return self.nomi
    
    def get_stock(self):
        """Mahsulot qoldig'ini hisoblash"""
        # Umumiy kirim
        total_kirim = InventoryTransaction.objects.filter(
            product=self,
            transaction_type='kirim'
        ).aggregate(total=Sum('miqdor'))['total'] or 0
        
        # Umumiy sotuvlar
        total_sales = SaleItems.objects.filter(
            product=self,
            sale__status='active'
        ).aggregate(total=Sum('miqdor'))['total'] or 0
        
        # Umumiy chiqim
        total_chiqim = InventoryTransaction.objects.filter(
            product=self,
            transaction_type='chiqim'
        ).aggregate(total=Sum('miqdor'))['total'] or 0
        
        return total_kirim - total_sales - total_chiqim
    
    def is_low_stock(self):
        """Mahsulot kam qolganligini tekshirish"""
        return self.get_stock() <= self.minimal_qoldiq


class InventoryTransaction(models.Model):
    """Sklad kirim-chiqim modeli"""
    TRANSACTION_TYPES = [
        ('kirim', _('Kirim')),
        ('chiqim', _('Chiqim')),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name=_("Mahsulot"))
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name=_("Tur"))
    miqdor = models.IntegerField(verbose_name=_("Miqdor"))
    sana = models.DateTimeField(auto_now_add=True, verbose_name=_("Sana"))
    izoh = models.TextField(null=True, blank=True, verbose_name=_("Izoh"))
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, verbose_name=_("Foydalanuvchi"))
    
    class Meta:
        verbose_name = _("Sklad harakati")
        verbose_name_plural = _("Sklad harakatlari")
        ordering = ['-sana']
    
    def __str__(self):
        return f"{self.product.nomi} - {self.get_transaction_type_display()} ({self.miqdor})"


class Sales(models.Model):
    """Sotuv modeli"""
    STATUS_CHOICES = [
        ('active', _('Faol')),
        ('cancelled', _('Bekor qilingan')),
    ]
    
    kassir = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, verbose_name=_("Kassir"))
    sana = models.DateTimeField(auto_now_add=True, verbose_name=_("Sana"))
    jami_summa = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Jami summa"))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', verbose_name=_("Status"))
    
    class Meta:
        verbose_name = _("Sotuv")
        verbose_name_plural = _("Sotuvlar")
        ordering = ['-sana']
    
    def __str__(self):
        return f"Sotuv #{self.id} - {self.jami_summa} " + str(_("so'm"))
    
    def calculate_total(self):
        """Jami summani hisoblash"""
        total = self.saleitems_set.aggregate(total=Sum('jami'))['total'] or 0
        return total


class SaleItems(models.Model):
    """Sotuv detallari modeli"""
    sale = models.ForeignKey(Sales, on_delete=models.CASCADE, verbose_name=_("Sotuv"))
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name=_("Mahsulot"))
    miqdor = models.IntegerField(verbose_name=_("Miqdor"))
    narx = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Narx"))
    jami = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Jami"))
    
    class Meta:
        verbose_name = _("Sotuv detali")
        verbose_name_plural = _("Sotuv detallari")
    
    def __str__(self):
        return f"{self.product.nomi} x {self.miqdor}"
    
    def save(self, *args, **kwargs):
        """Jami summani avtomatik hisoblash"""
        self.jami = self.miqdor * self.narx
        super().save(*args, **kwargs)
