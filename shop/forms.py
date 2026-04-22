from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _
from .models import Product, InventoryTransaction, Sales, SaleItems, CustomUser


class LoginForm(AuthenticationForm):
    """Login form"""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Foydalanuvchi nomi',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Parol'
        })
    )


class ProductForm(forms.ModelForm):
    """Mahsulot formasi"""
    class Meta:
        model = Product
        fields = ['nomi', 'kategoriya', 'narx', 'barcode', 'minimal_qoldiq']
        widgets = {
            'nomi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mahsulot nomi'}),
            'kategoriya': forms.Select(attrs={'class': 'form-select'}),
            'narx': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Narx'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Barcode (ixtiyoriy)'}),
            'minimal_qoldiq': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Minimal qoldiq'}),
        }


class InventoryTransactionForm(forms.ModelForm):
    """Sklad harakati formasi"""
    class Meta:
        model = InventoryTransaction
        fields = ['product', 'transaction_type', 'miqdor', 'izoh']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'miqdor': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Miqdor'}),
            'izoh': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Izoh (ixtiyoriy)'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        transaction_type = cleaned_data.get('transaction_type')
        miqdor = cleaned_data.get('miqdor')

        if miqdor is not None and miqdor <= 0:
            raise forms.ValidationError(_("Miqdor musbat bo'lishi kerak!"))

        if transaction_type == 'chiqim' and product and miqdor:
            current_stock = product.get_stock()
            if current_stock < miqdor:
                raise forms.ValidationError(
                    _("Skladda yetarli mahsulot yo'q! Joriy qoldiq: %(stock)s dona.") % {"stock": current_stock}
                )

        return cleaned_data


class SaleForm(forms.ModelForm):
    """Sotuv formasi"""
    class Meta:
        model = Sales
        fields = ['kassir']
        widgets = {
            'kassir': forms.Select(attrs={'class': 'form-select'}),
        }


class SaleItemForm(forms.ModelForm):
    """Sotuv detali formasi"""
    class Meta:
        model = SaleItems
        fields = ['product', 'miqdor', 'narx']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'miqdor': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Miqdor'}),
            'narx': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Narx'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Narxni avtomatik to'ldirish uchun
        if 'product' in self.data:
            try:
                product_id = int(self.data.get('product'))
                product = Product.objects.get(id=product_id)
                self.fields['narx'].initial = product.narx
            except (ValueError, Product.DoesNotExist):
                pass


class UserForm(forms.ModelForm):
    """Foydalanuvchi formasi"""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Parol'}),
        required=False
    )
    
    class Meta:
        model = CustomUser
        fields = ['username', 'fullname', 'role', 'telegram_id', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Foydalanuvchi nomi'}),
            'fullname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'To\'liq ism'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'telegram_id': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Telegram ID (ixtiyoriy)'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user
