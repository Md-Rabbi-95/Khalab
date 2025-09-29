from django import forms
from .models import Order, Payment


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['first_name','last_name', 'phone','email','address_line_1','address_line_2','country','state','city','order_note']


class PaymentForm(forms.Form):
    PAYMENT_METHOD_CHOICES = [
        ('COD', 'Cash on Delivery'),
        ('ONLINE', 'Online Payment'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('FULL', 'Full Payment'),
        ('ADVANCE', 'Advance Payment'),
    ]
    
    ONLINE_PAYMENT_CHOICES = [
        ('BKASH', 'Bkash'),
        ('NAGAD', 'Nagad'),
        ('ROCKET', 'Rocket'),
    ]
    
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        required=True
    )
    
    payment_type = forms.ChoiceField(
        choices=PAYMENT_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        required=True
    )
    
    online_payment_method = forms.ChoiceField(
        choices=ONLINE_PAYMENT_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        required=False
    )
    
    transaction_id = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter transaction ID'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        online_payment_method = cleaned_data.get('online_payment_method')
        transaction_id = cleaned_data.get('transaction_id')
        
        if payment_method == 'ONLINE':
            if not online_payment_method:
                raise forms.ValidationError("Please select an online payment method.")
            if not transaction_id:
                raise forms.ValidationError("Transaction ID is required for online payments.")
        
        return cleaned_data