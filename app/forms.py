"""
WTForms for the application.
MVP: Only region selection and price calculation forms.
"""
from flask_wtf import FlaskForm
from wtforms import SelectField, FloatField, SubmitField, StringField
from wtforms.validators import DataRequired, NumberRange, Optional, Length

class PostcodeForm(FlaskForm):
    """Form for entering UK postcode to auto-detect region."""
    postcode = StringField(
        'UK Postcode',
        validators=[
            DataRequired(message="Please enter a postcode"),
            Length(min=2, max=20, message="Postcode must be between 2 and 20 characters")
        ],
        render_kw={
            'placeholder': 'e.g., SW1A 1AA or SW1',
            'autocomplete': 'postal-code',
            'class': 'form-control'
        }
    )
    submit = SubmitField('View Prices')

class RegionSelectionForm(FlaskForm):
    """Form for manually selecting Octopus region (fallback)."""
    region = SelectField(
        'Region',
        choices=[],  # Populated dynamically from API
        validators=[DataRequired(message="Please select a region")]
    )
    submit = SubmitField('View Prices')

class ProductSelectionForm(FlaskForm):
    """Form for selecting Agile product."""
    product = SelectField(
        'Agile Tariff Version',
        choices=[],  # Populated dynamically from API
        validators=[DataRequired(message="Please select a tariff version")],
        render_kw={'class': 'form-select'}
    )
    submit = SubmitField('Select Tariff')

class PriceCalculationForm(FlaskForm):
    """Form for calculating cheapest charging block."""
    duration = FloatField(
        'Charging Duration (hours)',
        default=4.0,
        validators=[
            DataRequired(message="Please enter a duration"),
            NumberRange(min=0.5, max=6.0, message="Duration must be between 0.5 and 6 hours")
        ],
        render_kw={
            'step': '0.5',
            'min': '0.5',
            'max': '6.0',
            'placeholder': 'e.g., 3.5'
        }
    )
    capacity = FloatField(
        'Battery Capacity (kWh)',
        validators=[
            Optional(),
            NumberRange(min=0.1, max=100, message="Capacity must be between 0.1 and 100 kWh")
        ],
        render_kw={
            'step': '0.1',
            'min': '0.1',
            'placeholder': 'e.g., 10.0'
        }
    )
    submit = SubmitField('Calculate')

