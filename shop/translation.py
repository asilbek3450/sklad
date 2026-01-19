from modeltranslation.translator import register, TranslationOptions
from .models import Category, Product

@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ('nomi',)

@register(Product)
class ProductTranslationOptions(TranslationOptions):
    fields = ('nomi',)
