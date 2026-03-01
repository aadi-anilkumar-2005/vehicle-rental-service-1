from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required

def is_owner(user):
    return user.is_authenticated and hasattr(user, 'user_profile') and user.user_profile.role == 'owner'

def index_view(request):
    if is_owner(request.user):
        return redirect('owner_dashboard')
    return render(request, 'owner/index.html')

def login_view(request):
    if is_owner(request.user):
        return redirect('owner_dashboard')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user is not None:
            if is_owner(user):
                auth_login(request, user)
                return redirect('owner_dashboard')
            else:
                messages.error(request, "Access denied. You do not have owner privileges.")
        else:
            messages.error(request, "Invalid email or password.")
            
    return render(request, 'owner/login.html')

def register_view(request):
    return render(request, 'owner/register.html')

from django.db.models import Sum

@login_required(login_url='owner_login')
def dashboard_view(request):
    if not is_owner(request.user):
        return redirect('owner_login')

    from rentals.models import Booking, Vehicle, RentalShop
    
    shop = RentalShop.objects.annotate(v_count=models.Count('vehicles')).first()
    if not shop:
        shop = RentalShop.objects.create(name=f"{request.user.username}'s Shop", address="123 Main St", latitude=0, longitude=0)

    # 1. Total Revenue from completed bookings
    total_revenue = Booking.objects.filter(shop=shop, status='completed').aggregate(total=Sum('total_price'))['total'] or 0

    # 2. Active Bookings
    active_bookings = Booking.objects.filter(shop=shop, status__in=['active', 'upcoming']).count()

    # 3. Total Vehicles
    total_vehicles = Vehicle.objects.filter(shop=shop).count()

    # 4. Total Staff
    total_staff = User.objects.filter(user_profile__role='staff', is_active=True).count()

    # 5. Recent Bookings (top 5)
    recent_bookings = Booking.objects.filter(shop=shop).select_related('user', 'vehicle').order_by('-created_at')[:5]

    context = {
        'total_revenue': total_revenue,
        'active_bookings': active_bookings,
        'total_vehicles': total_vehicles,
        'total_staff': total_staff,
        'recent_bookings': recent_bookings,
    }

    return render(request, 'owner/dashboard.html', context)

from rentals.models import Booking
from staff.models import StaffTask

@login_required(login_url='owner_login')
def booking_management_view(request):
    if not is_owner(request.user):
        return redirect('owner_login')

    # Get the owner's shop (temporary fallback approach like in vehicle_management_view)
    shop = RentalShop.objects.annotate(v_count=models.Count('vehicles')).first()
    if not shop:
        shop = RentalShop.objects.create(name=f"{request.user.username}'s Shop", address="123 Main St", latitude=0, longitude=0)

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'assign_staff':
            booking_id = request.POST.get('booking_id')
            staff_id = request.POST.get('staff_id')
            
            try:
                print("ASSIGN STAFF ACTION:", booking_id, staff_id)
                booking = Booking.objects.get(id=booking_id, shop=shop)
                staff_member = User.objects.get(id=staff_id, user_profile__role='staff')
                
                print("FOUND BOOKING AND STAFF", booking, staff_member)
                
                # Delete any existing tasks for this booking to handle reassignments and orphaned tasks
                StaffTask.objects.filter(booking=booking).delete()
                
                # Create new Staff Task for the newly assigned staff member
                task_type = 'pickup' if booking.status == 'pickup_requested' else ('delivery' if booking.delivery_option == 'delivery' else 'pickup')
                task = StaffTask.objects.create(
                    booking=booking,
                    staff=staff_member,
                    type=task_type,
                    scheduled_time=booking.start_date,
                    status='pending'
                )
                
                # Note: Booking status remains the same since assignment shouldn't make it active.
                # It will be marked active or completed when staff completes the task.
                    
                messages.success(request, f"Assigned {staff_member.first_name} to Booking #{booking.id}")
            except Exception as e:
                messages.error(request, f"Error assigning staff: {str(e)}")
                
        return redirect('owner_bookings')

    bookings = Booking.objects.filter(shop=shop).select_related('user', 'vehicle').prefetch_related('staff_tasks__staff')
    staff_members = User.objects.filter(user_profile__role='staff', is_active=True).select_related('user_profile')
    
    return render(request, 'owner/bookingManagement.html', {
        'bookings': bookings,
        'staff_members': staff_members
    })

@login_required(login_url='owner_login')
def staff_management_view(request):
    if not is_owner(request.user):
        return redirect('owner_login')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            name = request.POST.get('name')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            password = request.POST.get('password')
            
            try:
                name_parts = name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ''
                
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                user.user_profile.role = 'staff'
                user.user_profile.phone = phone
                user.user_profile.save()
                messages.success(request, f"Staff member {name} added successfully!")
            except Exception as e:
                messages.error(request, f"Error adding staff: {str(e)}")
                
        elif action == 'edit':
            user_id = request.POST.get('user_id')
            name = request.POST.get('name')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            password = request.POST.get('password')

            try:
                user = User.objects.get(id=user_id, user_profile__role='staff')
                name_parts = name.split(' ', 1)
                user.first_name = name_parts[0]
                user.last_name = name_parts[1] if len(name_parts) > 1 else ''
                user.email = email
                user.username = email
                if password:
                    user.set_password(password)
                user.save()
                
                user.user_profile.phone = phone
                user.user_profile.save()
                messages.success(request, f"Staff member {name} updated successfully!")
            except Exception as e:
                messages.error(request, f"Error updating staff: {str(e)}")
                
        elif action == 'delete':
            user_id = request.POST.get('user_id')
            try:
                user = User.objects.get(id=user_id, user_profile__role='staff')
                user_name = f"{user.first_name} {user.last_name}".strip() or user.username
                user.delete()
                messages.success(request, f"Staff member {user_name} deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting staff: {str(e)}")
                
        return redirect('owner_staff')

    staff_users = User.objects.filter(user_profile__role='staff').select_related('user_profile')
    return render(request, 'owner/staffManagement.html', {'staff_users': staff_users})

from django.db import models
from rentals.models import Vehicle, RentalShop

@login_required(login_url='owner_login')
def vehicle_management_view(request):
    if not is_owner(request.user):
        return redirect('owner_login')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            try:
                # Find the owner's shop, or create a default owned by them if we are mapping them
                shop = RentalShop.objects.annotate(v_count=models.Count('vehicles')).first()
                if not shop:
                    shop = RentalShop.objects.create(name=f"{request.user.username}'s Shop", address="123 Main St", latitude=0, longitude=0)
                
                Vehicle.objects.create(
                    shop=shop,
                    type=request.POST.get('type'),
                    name=request.POST.get('name'),
                    brand=request.POST.get('brand'),
                    model=request.POST.get('model'),
                    number=request.POST.get('number'),
                    price_per_hour=request.POST.get('price_per_hour'),
                    price_per_day=request.POST.get('price_per_day'),
                    fuel_type=request.POST.get('fuel_type'),
                    transmission=request.POST.get('transmission'),
                    seating=request.POST.get('seating') or None,
                    features=[f.strip() for f in request.POST.get('features', '').split(',') if f.strip()],
                    images=[i.strip() for i in request.POST.get('images', '').split(',') if i.strip()],
                    is_available=request.POST.get('is_available', '') == 'on'
                )
                messages.success(request, f"Vehicle {request.POST.get('name')} added successfully!")
            except Exception as e:
                messages.error(request, f"Error adding vehicle: {str(e)}")
                
        elif action == 'edit':
            vehicle_id = request.POST.get('vehicle_id')
            try:
                vehicle = Vehicle.objects.get(id=vehicle_id)
                vehicle.type = request.POST.get('type')
                vehicle.name = request.POST.get('name')
                vehicle.brand = request.POST.get('brand')
                vehicle.model = request.POST.get('model')
                vehicle.number = request.POST.get('number')
                vehicle.price_per_hour = request.POST.get('price_per_hour')
                vehicle.price_per_day = request.POST.get('price_per_day')
                vehicle.fuel_type = request.POST.get('fuel_type')
                vehicle.transmission = request.POST.get('transmission')
                vehicle.seating = request.POST.get('seating') or None
                vehicle.features = [f.strip() for f in request.POST.get('features', '').split(',') if f.strip()]
                vehicle.images = [i.strip() for i in request.POST.get('images', '').split(',') if i.strip()]
                vehicle.is_available = request.POST.get('is_available', '') == 'on'
                vehicle.save()
                messages.success(request, f"Vehicle {vehicle.name} updated successfully!")
            except Exception as e:
                messages.error(request, f"Error updating vehicle: {str(e)}")
                
        elif action == 'delete':
            vehicle_id = request.POST.get('vehicle_id')
            try:
                vehicle = Vehicle.objects.get(id=vehicle_id)
                vehicle_name = vehicle.name
                vehicle.delete()
                messages.success(request, f"Vehicle {vehicle_name} deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting vehicle: {str(e)}")
                
        return redirect('owner_vehicles')

    vehicles = Vehicle.objects.all()
    return render(request, 'owner/vehicleManagement.html', {'vehicles': vehicles})

from django.contrib.auth import update_session_auth_hash

@login_required(login_url='owner_login')
def profile_view(request):
    if not is_owner(request.user):
        return redirect('owner_login')

    from rentals.models import RentalShop
    shop = RentalShop.objects.annotate(v_count=models.Count('vehicles')).first()
    if not shop:
        shop = RentalShop.objects.create(name=f"{request.user.username}'s Shop", address="123 Main St", latitude=0, longitude=0)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_general':
            try:
                user = request.user
                user.first_name = request.POST.get('first_name', user.first_name)
                user.last_name = request.POST.get('last_name', user.last_name)
                user.email = request.POST.get('email', user.email)
                user.save()
                
                profile = user.user_profile
                profile.phone = request.POST.get('phone', profile.phone)
                profile.save()
                
                messages.success(request, "General profile updated successfully!")
            except Exception as e:
                messages.error(request, f"Error updating general profile: {str(e)}")
            return redirect('owner_profile')

        elif action == 'update_shop':
            try:
                shop.name = request.POST.get('shop_name', shop.name)
                shop.address = request.POST.get('address', shop.address)
                shop.operating_hours = request.POST.get('operating_hours', shop.operating_hours)
                
                # Handle potentially empty float fields
                lat = request.POST.get('latitude')
                lng = request.POST.get('longitude')
                if lat: shop.latitude = float(lat)
                if lng: shop.longitude = float(lng)
                
                shop.save()
                messages.success(request, "Shop information updated successfully!")
            except ValueError:
                messages.error(request, "Invalid latitude or longitude format.")
            except Exception as e:
                messages.error(request, f"Error updating shop info: {str(e)}")
                
            return redirect('owner_profile')

        elif action == 'change_password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if not request.user.check_password(current_password):
                messages.error(request, "Current password is incorrect.")
            elif new_password != confirm_password:
                messages.error(request, "New passwords do not match.")
            elif len(new_password) < 8:
                messages.error(request, "New password must be at least 8 characters long.")
            else:
                try:
                    request.user.set_password(new_password)
                    request.user.save()
                    update_session_auth_hash(request, request.user)  # Keep user logged in
                    messages.success(request, "Security settings updated successfully!")
                except Exception as e:
                    messages.error(request, f"Error updating password: {str(e)}")
                    
            return redirect('owner_profile')

    return render(request, 'owner/Profile.html', {'shop': shop})

def logout_view(request):
    auth_logout(request)
    return redirect('owner_login')

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@login_required(login_url='owner_login')
def staff_api(request):
    if not is_owner(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if request.method == 'GET':
        staff_users = User.objects.filter(user_profile__role='staff').select_related('user_profile')
        data = []
        for u in staff_users:
            data.append({
                'id': u.id,
                'name': f"{u.first_name} {u.last_name}".strip() or u.username,
                'email': u.email,
                'phone': u.user_profile.phone if hasattr(u, 'user_profile') else '',
                'role': 'Staff',
                'status': 'active' if u.is_active else 'inactive',
                'joinDate': u.date_joined.strftime('%Y-%m-%d')
            })
        return JsonResponse({'staff': data})

    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
            name_parts = body.get('name', '').split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            user = User.objects.create_user(
                username=body.get('email'),
                email=body.get('email'),
                password=body.get('password'),
                first_name=first_name,
                last_name=last_name
            )
            user.user_profile.role = body.get('role', 'staff').lower()
            user.user_profile.phone = body.get('phone', '')
            user.user_profile.save()
            
            return JsonResponse({'success': True, 'id': user.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    elif request.method == 'DELETE':
        try:
            body = json.loads(request.body)
            user_id = body.get('id')
            User.objects.filter(id=user_id, user_profile__role='staff').delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


# ── Chat View ──────────────────────────────────────────────────────────────────

@login_required(login_url='owner_login')
def chat_view(request):
    if not is_owner(request.user):
        return redirect('owner_login')

    from rentals.models import Conversation, Message, RentalShop

    shop = RentalShop.objects.annotate(v_count=models.Count('vehicles')).first()
    if not shop:
        shop = RentalShop.objects.create(
            name=f"{request.user.username}'s Shop", address="123 Main St", latitude=0, longitude=0
        )

    selected_conversation = None
    conversation_messages = []

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'send_message':
            conv_id = request.POST.get('conversation_id')
            text = request.POST.get('text', '').strip()
            if conv_id and text:
                try:
                    conv = Conversation.objects.get(id=conv_id, shop=shop)
                    Message.objects.create(
                        conversation=conv,
                        sender=request.user,
                        sender_role='owner',
                        text=text,
                    )
                except Exception as e:
                    messages.error(request, f"Error sending message: {e}")
        conv_id = request.POST.get('conversation_id', '')
        from django.urls import reverse
        return redirect(f"{reverse('owner_chat')}?conv={conv_id}")

    conv_id = request.GET.get('conv')
    conversations = Conversation.objects.filter(shop=shop).select_related('user').order_by('-updated_at')

    if conv_id:
        try:
            selected_conversation = conversations.get(id=conv_id)
            conversation_messages = selected_conversation.messages.all().order_by('created_at')
            # Mark messages as read
            selected_conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        except Conversation.DoesNotExist:
            pass

    return render(request, 'owner/chat.html', {
        'conversations': conversations,
        'selected_conversation': selected_conversation,
        'conversation_messages': conversation_messages,
    })


# ── Reviews View ───────────────────────────────────────────────────────────────

@login_required(login_url='owner_login')
def reviews_view(request):
    if not is_owner(request.user):
        return redirect('owner_login')

    from rentals.models import Review, RentalShop
    from django.utils import timezone

    shop = RentalShop.objects.annotate(v_count=models.Count('vehicles')).first()
    if not shop:
        shop = RentalShop.objects.create(
            name=f"{request.user.username}'s Shop", address="123 Main St", latitude=0, longitude=0
        )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'reply':
            review_id = request.POST.get('review_id')
            reply_text = request.POST.get('reply_text', '').strip()
            if review_id and reply_text:
                try:
                    review = Review.objects.get(id=review_id, shop=shop)
                    review.owner_reply = reply_text
                    review.replied_at = timezone.now()
                    review.save()
                    messages.success(request, "Reply posted successfully!")
                except Review.DoesNotExist:
                    messages.error(request, "Review not found.")
                except Exception as e:
                    messages.error(request, f"Error posting reply: {e}")
        return redirect('owner_reviews')

    all_reviews = Review.objects.filter(shop=shop).select_related('user')

    # Compute average rating
    total = all_reviews.count()
    avg_rating = 0
    if total:
        avg_rating = round(sum(r.rating for r in all_reviews) / total, 1)

    replied_count = all_reviews.filter(owner_reply__isnull=False).exclude(owner_reply='').count()
    pending_count = all_reviews.filter(owner_reply__isnull=True).count() + all_reviews.filter(owner_reply='').count()

    return render(request, 'owner/reviews.html', {
        'reviews': all_reviews,
        'avg_rating': avg_rating,
        'total_reviews': total,
        'replied_count': replied_count,
        'pending_count': pending_count,
    })


# ── Complaints View ────────────────────────────────────────────────────────────

@login_required(login_url='owner_login')
def complaints_view(request):
    if not is_owner(request.user):
        return redirect('owner_login')

    from rentals.models import Complaint, RentalShop

    shop = RentalShop.objects.annotate(v_count=models.Count('vehicles')).first()
    if not shop:
        shop = RentalShop.objects.create(
            name=f"{request.user.username}'s Shop", address="123 Main St", latitude=0, longitude=0
        )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign_staff':
            complaint_id = request.POST.get('complaint_id')
            staff_id = request.POST.get('staff_id')
            try:
                complaint = Complaint.objects.get(id=complaint_id, shop=shop)
                staff_member = User.objects.get(id=staff_id, user_profile__role='staff')
                complaint.assigned_to = staff_member
                complaint.status = 'assigned'
                complaint.save()
                messages.success(request, f"Complaint #{complaint_id} assigned to {staff_member.first_name}.")
            except Complaint.DoesNotExist:
                messages.error(request, "Complaint not found.")
            except User.DoesNotExist:
                messages.error(request, "Staff member not found.")
            except Exception as e:
                messages.error(request, f"Error assigning complaint: {e}")
        elif action == 'resolve':
            complaint_id = request.POST.get('complaint_id')
            try:
                complaint = Complaint.objects.get(id=complaint_id, shop=shop)
                complaint.status = 'resolved'
                complaint.save()
                messages.success(request, f"Complaint #{complaint_id} marked as resolved.")
            except Exception as e:
                messages.error(request, f"Error resolving complaint: {e}")
        return redirect('owner_complaints')

    all_complaints = Complaint.objects.filter(shop=shop).select_related('user', 'booking', 'assigned_to')
    staff_members = User.objects.filter(user_profile__role='staff', is_active=True).select_related('user_profile')

    return render(request, 'owner/complaints.html', {
        'complaints': all_complaints,
        'staff_members': staff_members,
    })


# ── KYC Management View ────────────────────────────────────────────────────────

@login_required(login_url='owner_login')
def kyc_management_view(request):
    if not is_owner(request.user):
        return redirect('owner_login')

    from rentals.models import KYCDocument
    from django.utils import timezone

    if request.method == 'POST':
        action = request.POST.get('action')
        kyc_id = request.POST.get('kyc_id')

        try:
            kyc = KYCDocument.objects.get(id=kyc_id)

            if action == 'approve':
                kyc.status = 'verified'
                kyc.verified_at = timezone.now()
                kyc.rejection_reason = None
                kyc.reviewed_by = request.user
                kyc.save()
                messages.success(request, f"KYC for {kyc.full_name} has been approved.")

            elif action == 'reject':
                reason = request.POST.get('rejection_reason', '').strip()
                if not reason:
                    messages.error(request, "Please provide a rejection reason.")
                else:
                    kyc.status = 'rejected'
                    kyc.rejection_reason = reason
                    kyc.verified_at = None
                    kyc.reviewed_by = request.user
                    kyc.save()
                    messages.success(request, f"KYC for {kyc.full_name} has been rejected.")

        except KYCDocument.DoesNotExist:
            messages.error(request, "KYC record not found.")
        except Exception as e:
            messages.error(request, f"Error processing KYC action: {str(e)}")

        return redirect('owner_kyc')

    # GET – list KYC documents with optional status filter
    status_filter = request.GET.get('status', '')
    kyc_docs = KYCDocument.objects.select_related('user', 'reviewed_by').order_by('-submitted_at')

    if status_filter in ('pending', 'verified', 'rejected', 'not_submitted'):
        kyc_docs = kyc_docs.filter(status=status_filter)

    counts = {
        'total': KYCDocument.objects.count(),
        'pending': KYCDocument.objects.filter(status='pending').count(),
        'verified': KYCDocument.objects.filter(status='verified').count(),
        'rejected': KYCDocument.objects.filter(status='rejected').count(),
    }

    return render(request, 'owner/kycManagement.html', {
        'kyc_docs': kyc_docs,
        'status_filter': status_filter,
        'counts': counts,
    })


# ── KYC Detail View ────────────────────────────────────────────────────────────

@login_required(login_url='owner_login')
def kyc_detail_view(request, kyc_id):
    if not is_owner(request.user):
        return redirect('owner_login')

    from rentals.models import KYCDocument
    from django.utils import timezone

    try:
        kyc = KYCDocument.objects.select_related('user', 'reviewed_by').get(id=kyc_id)
    except KYCDocument.DoesNotExist:
        messages.error(request, "KYC record not found.")
        return redirect('owner_kyc')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            kyc.status = 'verified'
            kyc.verified_at = timezone.now()
            kyc.rejection_reason = None
            kyc.reviewed_by = request.user
            kyc.save()
            messages.success(request, f"KYC for {kyc.full_name} has been approved successfully.")
            return redirect('owner_kyc')

        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '').strip()
            if not reason:
                messages.error(request, "Please provide a rejection reason.")
            else:
                kyc.status = 'rejected'
                kyc.rejection_reason = reason
                kyc.verified_at = None
                kyc.reviewed_by = request.user
                kyc.save()
                messages.success(request, f"KYC for {kyc.full_name} has been rejected.")
                return redirect('owner_kyc')

    return render(request, 'owner/kycDetail.html', {'kyc': kyc})

