from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from modeltranslation.admin import TranslationAdmin
from .models import CustomUser, Product, InventoryTransaction, Sales, SaleItems, Category

@admin.register(Category)
class CategoryAdmin(TranslationAdmin):
    list_display = ('nomi',)
    search_fields = ('nomi',)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Foydalanuvchi admin paneli"""
    list_display = ['username', 'fullname', 'role', 'telegram_id', 'is_active']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['username', 'fullname', 'telegram_id']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Qo\'shimcha ma\'lumotlar', {
            'fields': ('telegram_id', 'role', 'fullname')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Qo\'shimcha ma\'lumotlar', {
            'fields': ('telegram_id', 'role', 'fullname')
        }),
    )


@admin.register(Product)
class ProductAdmin(TranslationAdmin):
    """Mahsulot admin paneli"""
    list_display = ['nomi', 'kategoriya', 'narx', 'barcode', 'get_stock_display', 'minimal_qoldiq', 'created_at']
    list_filter = ['kategoriya', 'created_at']
    search_fields = ['nomi', 'barcode']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_stock_display(self, obj):
        stock = obj.get_stock()
        if obj.is_low_stock():
            return f"⚠️ {stock}"
        return stock
    get_stock_display.short_description = "Qoldiq"


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    """Sklad harakatlari admin paneli"""
    list_display = ['product', 'transaction_type', 'miqdor', 'user', 'sana']
    list_filter = ['transaction_type', 'sana']
    search_fields = ['product__nomi']
    readonly_fields = ['sana']
    autocomplete_fields = ['product', 'user']


class SaleItemsInline(admin.TabularInline):
    """Sotuv detallari inline"""
    model = SaleItems
    extra = 1
    autocomplete_fields = ['product']
    readonly_fields = ['jami']


@admin.register(Sales)
class SalesAdmin(admin.ModelAdmin):
    """Sotuvlar admin paneli"""
    list_display = ['id', 'kassir', 'jami_summa', 'status', 'sana']
    list_filter = ['status', 'sana']
    search_fields = ['kassir__fullname']
    readonly_fields = ['sana']
    autocomplete_fields = ['kassir']
    inlines = [SaleItemsInline]
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Jami summani qayta hisoblash
        obj.jami_summa = obj.calculate_total()
        obj.save()


@admin.register(SaleItems)
class SaleItemsAdmin(admin.ModelAdmin):
    """Sotuv detallari admin paneli"""
    list_display = ['sale', 'product', 'miqdor', 'narx', 'jami']
    search_fields = ['product__nomi']
    autocomplete_fields = ['sale', 'product']
    readonly_fields = ['jami']
