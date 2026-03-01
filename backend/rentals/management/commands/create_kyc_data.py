from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rentals.models import KYCDocument, UserProfile
from django.utils import timezone
import random
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Create temporary KYC data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating temporary KYC data...')

        # Sample data
        sample_kyc_data = [
            {
                'username': 'john_doe',
                'email': 'john.doe@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'full_name': 'John Michael Doe',
                'date_of_birth': '1990-05-15',
                'address': '123 Main Street, New York, NY 10001',
                'phone': '+1 555-0123',
                'kyc_email': 'john.doe@example.com',
                'driving_license_number': 'DL123456789',
                'secondary_doc_type': 'aadhar',
                'secondary_doc_number': '1234-5678-9012',
                'status': 'pending'
            },
            {
                'username': 'jane_smith',
                'email': 'jane.smith@example.com',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'full_name': 'Jane Elizabeth Smith',
                'date_of_birth': '1985-08-22',
                'address': '456 Oak Avenue, Los Angeles, CA 90001',
                'phone': '+1 555-0124',
                'kyc_email': 'jane.smith@example.com',
                'driving_license_number': 'DL987654321',
                'secondary_doc_type': 'passport',
                'secondary_doc_number': 'P12345678',
                'status': 'verified'
            },
            {
                'username': 'bob_wilson',
                'email': 'bob.wilson@example.com',
                'first_name': 'Bob',
                'last_name': 'Wilson',
                'full_name': 'Robert James Wilson',
                'date_of_birth': '1992-12-03',
                'address': '789 Pine Road, Chicago, IL 60601',
                'phone': '+1 555-0125',
                'kyc_email': 'bob.wilson@example.com',
                'driving_license_number': 'DL456789123',
                'secondary_doc_type': 'voter',
                'secondary_doc_number': 'VOT987654',
                'status': 'rejected',
                'rejection_reason': 'Driving license photo is blurry and unclear. Please upload a clear photo of your license.'
            },
            {
                'username': 'alice_brown',
                'email': 'alice.brown@example.com',
                'first_name': 'Alice',
                'last_name': 'Brown',
                'full_name': 'Alice Marie Brown',
                'date_of_birth': '1988-03-17',
                'address': '321 Elm Street, Houston, TX 77001',
                'phone': '+1 555-0126',
                'kyc_email': 'alice.brown@example.com',
                'driving_license_number': 'DL789123456',
                'secondary_doc_type': 'pan',
                'secondary_doc_number': 'PANABCD1234',
                'status': 'pending'
            },
            {
                'username': 'charlie_davis',
                'email': 'charlie.davis@example.com',
                'first_name': 'Charlie',
                'last_name': 'Davis',
                'full_name': 'Charles Michael Davis',
                'date_of_birth': '1995-07-09',
                'address': '654 Maple Drive, Phoenix, AZ 85001',
                'phone': '+1 555-0127',
                'kyc_email': 'charlie.davis@example.com',
                'driving_license_number': 'DL321654987',
                'secondary_doc_type': 'national_id',
                'secondary_doc_number': 'NID5678901234',
                'status': 'verified'
            }
        ]

        created_count = 0
        updated_count = 0

        for data in sample_kyc_data:
            try:
                # Create or get user
                user, created = User.objects.get_or_create(
                    username=data['username'],
                    defaults={
                        'email': data['email'],
                        'first_name': data['first_name'],
                        'last_name': data['last_name'],
                        'date_joined': timezone.now() - timedelta(days=random.randint(1, 365))
                    }
                )

                if created:
                    # Set password for new users
                    user.set_password('password123')
                    user.save()
                    created_count += 1
                else:
                    updated_count += 1

                # Create or get user profile
                profile, profile_created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'role': 'user',
                        'phone': data['phone'],
                        'address': data['address']
                    }
                )
                
                if not profile_created:
                    # Update existing profile
                    profile.phone = data['phone']
                    profile.address = data['address']
                    profile.save()

                # Create or update KYC document
                kyc, kyc_created = KYCDocument.objects.get_or_create(
                    user=user,
                    defaults={
                        'full_name': data['full_name'],
                        'date_of_birth': datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date(),
                        'address': data['address'],
                        'phone': data['phone'],
                        'email': data['kyc_email'],
                        'driving_license_number': data['driving_license_number'],
                        'secondary_doc_type': data['secondary_doc_type'],
                        'secondary_doc_number': data['secondary_doc_number'],
                        'status': data['status'],
                        'submitted_at': timezone.now() - timedelta(hours=random.randint(1, 720)),
                        'rejection_reason': data.get('rejection_reason', '')
                    }
                )

                if not kyc_created:
                    # Update existing KYC
                    kyc.full_name = data['full_name']
                    kyc.date_of_birth = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
                    kyc.address = data['address']
                    kyc.phone = data['phone']
                    kyc.email = data['kyc_email']
                    kyc.driving_license_number = data['driving_license_number']
                    kyc.secondary_doc_type = data['secondary_doc_type']
                    kyc.secondary_doc_number = data['secondary_doc_number']
                    kyc.status = data['status']
                    kyc.rejection_reason = data.get('rejection_reason', '')
                    kyc.save()

                # Set verified_at and reviewed_by for verified/rejected KYCs
                if data['status'] in ['verified', 'rejected']:
                    # Get first admin/owner user as reviewer
                    reviewer = User.objects.filter(
                        user_profile__role__in=['admin', 'owner']
                    ).first()
                    
                    if reviewer:
                        kyc.reviewed_by = reviewer
                        if data['status'] == 'verified':
                            kyc.verified_at = timezone.now() - timedelta(hours=random.randint(1, 24))
                        kyc.save()

                status_icon = {
                    'pending': '⏳',
                    'verified': '✅', 
                    'rejected': '❌'
                }.get(data['status'], '📋')

                self.stdout.write(
                    f'{status_icon} {data["full_name"]} ({data["status"]})'
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error creating KYC for {data["username"]}: {str(e)}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ KYC data creation completed!\n'
                f'📊 Summary:\n'
                f'   • New users created: {created_count}\n'
                f'   • Existing users updated: {updated_count}\n'
                f'   • Total KYC records: {len(sample_kyc_data)}\n\n'
                f'🔑 Default password for all users: password123\n'
                f'🌐 You can now view KYC management at: /kycManagement.html'
            )
        )
