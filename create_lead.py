import xmlrpc.client

# Odoo connection details
url = "http://localhost:8069"
db = "odoo"
username = "admin"
password = "admin"

# Common Odoo XML-RPC endpoints
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

if uid:
    print("Authentication successful. User ID:", uid)
    try:
        # Create a new lead (crm.lead)
        lead_id = models.execute_kw(db, uid, password, 'crm.lead', 'create', [{
            'name': 'Sample Lead from XML-RPC',
            'contact_name': 'John Doe',
            'email_from': 'john.doe@example.com',
            'phone': '123-456-7890',
            'description': 'This is a sample lead created via XML-RPC API for testing purposes.',
        }])
        print(f"Successfully created lead with ID: {lead_id}")

    except xmlrpc.client.Fault as err:
        print(f"Error creating lead: {err.faultCode} - {err.faultString}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
else:
    print("Authentication failed.")
