# orders/forms.py
from django import forms
from .models import Order, Payment

# Bangladesh districts list
BANGLADESH_DISTRICTS = [
    ('Bagerhat', 'Bagerhat'),
    ('Bandarban', 'Bandarban'),
    ('Barguna', 'Barguna'),
    ('Barisal', 'Barisal'),
    ('Bhola', 'Bhola'),
    ('Bogra', 'Bogra'),
    ('Brahmanbaria', 'Brahmanbaria'),
    ('Cumilla', 'Cumilla'),
    ('Chandpur', 'Chandpur'),
    ('Chattogram', 'Chattogram'),
    ('Chuadanga', 'Chuadanga'),
    ("Cox's Bazar", "Cox's Bazar"),
    ('Chapainawabganj','Chapainawabganj'),
    ('Dhaka', 'Dhaka'),
    ('Dinajpur', 'Dinajpur'),
    ('Faridpur', 'Faridpur'),
    ('Feni', 'Feni'),
    ('Gaibandha', 'Gaibandha'),
    ('Gazipur', 'Gazipur'),
    ('Gopalganj', 'Gopalganj'),
    ('Habiganj', 'Habiganj'),
    ('Jamalpur', 'Jamalpur'),
    ('Jashore', 'Jashore'),
    ('Jhalokati', 'Jhalokati'),
    ('Jhenaidah', 'Jhenaidah'),
    ('Joypurhat', 'Joypurhat'),
    ('Khagrachari', 'Khagrachari'),
    ('Khulna', 'Khulna'),
    ('Kishoreganj', 'Kishoreganj'),
    ('Kurigram', 'Kurigram'),
    ('Kushtia', 'Kushtia'),
    ('Lakshmipur', 'Lakshmipur'),
    ('Lalmonirhat', 'Lalmonirhat'),
    ('Madaripur', 'Madaripur'),
    ('Magura', 'Magura'),
    ('Manikganj', 'Manikganj'),
    ('Meherpur', 'Meherpur'),
    ('Moulvibazar', 'Moulvibazar'),
    ('Munshiganj', 'Munshiganj'),
    ('Mymensingh', 'Mymensingh'),
    ('Naogaon', 'Naogaon'),
    ('Narayanganj', 'Narayanganj'),
    ('Narsingdi', 'Narsingdi'),
    ('Natore', 'Natore'),
    ('Narail', 'Narail'),
    ('Netrokona', 'Netrokona'),
    ('Nilphamari', 'Nilphamari'),
    ('Noakhali', 'Noakhali'),
    ('Pabna', 'Pabna'),
    ('Panchagarh', 'Panchagarh'),
    ('Patuakhali', 'Patuakhali'),
    ('Pirojpur', 'Pirojpur'),
    ('Rajbari', 'Rajbari'),
    ('Rajshahi', 'Rajshahi'),
    ('Rangamati', 'Rangamati'),
    ('Rangpur', 'Rangpur'),
    ('Savar', 'Savar'),
    ('Satkhira', 'Satkhira'),
    ('Shariatpur', 'Shariatpur'),
    ('Sherpur', 'Sherpur'),
    ('Sirajganj', 'Sirajganj'),
    ('Sunamganj', 'Sunamganj'),
    ('Sylhet', 'Sylhet'),
    ('Tangail', 'Tangail'),
    ('Thakurgaon', 'Thakurgaon'),
]


class OrderForm(forms.ModelForm):
    state = forms.ChoiceField(
        choices=BANGLADESH_DISTRICTS,
        widget=forms.Select(attrs={
            'class': 'custom-select',
            'required': 'required'
        }),
        label='District'
    )
    
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'phone', 'email', 'address_line_1', 
                  'address_line_2', 'area' ,'country', 'state', 'order_note']
        
    def __init__(self, *args, **kwargs):
        super(OrderForm, self).__init__(*args, **kwargs)
        
        # Add Bootstrap classes and placeholders
        self.fields['first_name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'e.g. Arif',
            'required': 'required'
        })
        self.fields['last_name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'e.g. Hossain',
            'required': 'required'
        })
        self.fields['phone'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '01XXXXXXXXX',
            'required': 'required'
        })
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'you@example.com',
            'required': 'required'
        })
        self.fields['address_line_1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'House, Road, Block',
            'required': 'required'
        })
        self.fields['address_line_2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Area / Landmark (optional)'
        })
        self.fields['area'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Area/Locality (e.g., Gulshan, Dhanmondi)'
        })
        self.fields['country'].widget.attrs.update({
            'class': 'form-control',
            'value': 'Bangladesh',
            'readonly': 'readonly'
        })
        self.fields['order_note'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Additional instructions (optional)',
            'rows': '3'
        })

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not phone:
            raise forms.ValidationError('Phone number is required.')
        if not phone.isdigit():
            raise forms.ValidationError('Phone number must contain only digits.')
        if len(phone) < 11:
            raise forms.ValidationError('Phone number must be at least 11 digits.')
        return phone

    def clean_state(self):
        state = self.cleaned_data.get('state')
        if not state:
            raise forms.ValidationError('Please select a district.')
        return state


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