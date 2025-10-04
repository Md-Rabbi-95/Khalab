# courier/services.py
import requests
import logging
from .models import REDXConfiguration, REDXParcel

logger = logging.getLogger(__name__)


class REDXService:
    """Service class to interact with REDX API"""
    
    def __init__(self):
        try:
            self.config = REDXConfiguration.objects.filter(is_active=True).first()
            if not self.config:
                raise Exception("REDX Configuration not found. Please configure REDX in admin panel.")
            self.base_url = self.config.get_base_url().rstrip('/')
            self.token = self.config.get_token()
        except Exception as e:
            logger.error(f"REDX Configuration Error: {str(e)}")
            raise
    
    def get_headers(self):
        """Get API headers with proper Bearer token format"""
        token = self.token.strip()
        
        # If token doesn't start with 'Bearer ', add it
        if not token.startswith('Bearer '):
            token = f'Bearer {token}'
        
        return {
            'Content-Type': 'application/json',
            'API-ACCESS-TOKEN': token
        }
    
    def get_areas(self):
        """Get list of available areas"""
        url = f"{self.base_url}/areas"
        
        try:
            logger.info("Fetching REDX areas")
            
            response = requests.get(
                url,
                headers=self.get_headers(),
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            return {
                'success': True,
                'data': data.get('areas', [])
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"REDX Areas Error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    def find_area_by_name(self, area_name, district_name='Dhaka'):
        """Find area ID by name or district"""
        result = self.get_areas()
        if not result['success']:
            return None
        
        areas = result['data']
        
        # Try exact match first
        for area in areas:
            if area['name'].lower() == area_name.lower() and area['district_name'] == district_name:
                return area
        
        # Try partial match
        for area in areas:
            if area_name.lower() in area['name'].lower() and area['district_name'] == district_name:
                return area
        
        # Fallback to first area in district
        for area in areas:
            if area['district_name'] == district_name:
                return area
        
        # Ultimate fallback
        return areas[0] if areas else None
    
    def create_parcel(self, parcel_data):
        """
        Create a parcel in REDX system
        
        Args:
            parcel_data (dict): Parcel information with REDX required fields
            
        Returns:
            dict: API response with success status and tracking_id
        """
        url = f"{self.base_url}/parcel"
        
        try:
            logger.info(f"Creating REDX parcel: {parcel_data.get('merchant_invoice_id')}")
            logger.debug(f"Request URL: {url}")
            logger.debug(f"Request payload: {parcel_data}")
            
            response = requests.post(
                url,
                json=parcel_data,
                headers=self.get_headers(),
                timeout=30
            )
            
            logger.debug(f"Response Status: {response.status_code}")
            logger.debug(f"Response Body: {response.text}")
            
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            
            # Extract tracking ID
            tracking_id = response_data.get('tracking_id')
            
            if not tracking_id:
                logger.warning(f"No tracking ID found in response: {response_data}")
                return {
                    'success': False,
                    'error': 'Parcel created but no tracking ID returned',
                    'data': response_data
                }
            
            logger.info(f"Parcel created successfully. Tracking ID: {tracking_id}")
            
            return {
                'success': True,
                'data': response_data,
                'tracking_id': tracking_id
            }
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"REDX API HTTP Error: {e}")
            error_message = self._extract_error_message(e)
            
            return {
                'success': False,
                'error': error_message,
                'status_code': e.response.status_code if e.response else None
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"REDX API Request Error: {str(e)}")
            return {
                'success': False,
                'error': f"Network error: {str(e)}"
            }
            
        except Exception as e:
            logger.exception("Unexpected error during parcel creation")
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    def _extract_error_message(self, exception):
        """Extract error message from HTTP exception"""
        if not hasattr(exception, 'response') or exception.response is None:
            return str(exception)
        
        try:
            error_data = exception.response.json()
            
            # Try different error message fields
            if 'message' in error_data:
                return error_data['message']
            elif 'error' in error_data:
                if isinstance(error_data['error'], dict):
                    return error_data['error'].get('message', str(error_data['error']))
                return str(error_data['error'])
            elif 'errors' in error_data:
                if isinstance(error_data['errors'], list) and error_data['errors']:
                    return str(error_data['errors'][0])
                return str(error_data['errors'])
            elif 'validation_errors' in error_data:
                return f"Validation errors: {error_data['validation_errors']}"
            
            return str(error_data)
            
        except:
            return exception.response.text or str(exception)
    
    def track_parcel(self, tracking_id):
        """Track a parcel status"""
        url = f"{self.base_url}/parcel/track/{tracking_id}"
        
        try:
            logger.info(f"Tracking parcel: {tracking_id}")
            
            response = requests.get(
                url,
                headers=self.get_headers(),
                timeout=30
            )
            
            logger.debug(f"Track Response Status: {response.status_code}")
            logger.debug(f"Track Response Body: {response.text}")
            
            response.raise_for_status()
            
            response_data = response.json()
            
            return {
                'success': True,
                'data': response_data
            }
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"REDX Tracking HTTP Error: {e}")
            error_message = self._extract_error_message(e)
            
            return {
                'success': False,
                'error': error_message
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"REDX Tracking Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_parcel(self, tracking_id):
        """Cancel a parcel"""
        url = f"{self.base_url}/parcel/cancel/{tracking_id}"
        
        try:
            logger.info(f"Cancelling parcel: {tracking_id}")
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                timeout=30
            )
            
            logger.debug(f"Cancel Response Status: {response.status_code}")
            logger.debug(f"Cancel Response Body: {response.text}")
            
            response.raise_for_status()
            
            return {
                'success': True,
                'data': response.json()
            }
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"REDX Cancel HTTP Error: {e}")
            error_message = self._extract_error_message(e)
            
            return {
                'success': False,
                'error': error_message
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"REDX Cancel Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def test_connection(self):
        """Test REDX API connection"""
        try:
            result = self.get_areas()
            return result['success']
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False