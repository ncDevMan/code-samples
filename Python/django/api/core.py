# Here we will add the core functions to the API. These will include get and set methods to CRUD the database

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from datetime import datetime
from dateutil import parser
from cerberus import Validator
from decimal import Decimal



from django.contrib.auth.models import User
from lien.models import *
from reporting.reports import *
from reporting.models import *






# ------------------------- Lien Section -------------------------

def get_other_liens(lien, id):
    lien = get_object_or_404(Lien, pk=id)
    # Other liens with the same map number
    liens_w_mapno = Lien.objects.filter(
        map_number=lien.map_number,
        county = lien.county
    )
    # Remove duplicate liens
    other_liens = [
        l for l in liens_w_mapno
        if l != lien
    ]

    return other_liens



# ------------------------- Users Section -------------------------

def get_all_users():

    users = User.objects.all()

    return users


def get_user_by_id(id):


    user = User.objects.filter(id = id)

    return user




# ------------------------- Notes Section -------------------------
def get_note_by_id(id):
    note = Notes.objects.filter(id = id)

    return note


def get_notes_by_user(user):

    notes = Notes.objects.filter(user = user)

    return notes


def create_note(body, lien, user):

    note = Note.objects.create(body=body, user=user, lien=lien)

    note.save()

    return note.id




# ------------------------- Notification Section -------------------------

def get_all_tasks_for_recepient(user):
    tasks = NotificationReport.objects.filter(user = user)

    return tasks








# ------------------------- Calculations Section -------------------------

def get_face_amount(lien_list, associated_properties = False):
    # The face amount is actually Lien Amount in the system
    # Unpaid Bills
    
    total = 0

    for l in lien_list:
        lien = get_object_or_404(Lien, pk=int(l))
        total += Decimal(lien.lien_amount)
        if associated_properties:
            other_liens = get_other_liens(lien, lien.id)
            for ol in other_liens:
                if ol.date_paid is None:
                    total += Decimal(ol.lien_amount)

    return total




def get_interest_amount(lien_list, associated_properties = False):
    # The face amount is actually Lien Amount in the system
    # Unpaid Bills
    
    total = 0

    for l in lien_list:
        lien = get_object_or_404(Lien, pk=int(l))
        total += Decimal(lien.total_interest)
        if associated_properties:
            other_liens = get_other_liens(lien, lien.id)
            for ol in other_liens:
                if ol.date_paid is None:
                    total += Decimal(ol.total_interest)
                
    return total



def get_interest_amount(lien_list, associated_properties = False):
    # The face amount is actually Lien Amount in the system
    # Unpaid Bills
    
    total = 0

    for l in lien_list:
        lien = get_object_or_404(Lien, pk=int(l))
        total += Decimal(lien.total_interest)
        if associated_properties:
            other_liens = get_other_liens(lien, lien.id)
            for ol in other_liens:
                if ol.date_paid is None:
                    total += Decimal(ol.total_interest)
                
    return total



def get_foreclosure_costs_amount(lien_list, associated_properties = False):
    # Foreclosure Costs paid by entity
    # Unpaid Bills
    
    total = 0

    for l in lien_list:
        lien = get_object_or_404(Lien, pk=int(l))
        total += Decimal(lien.foreclosure_costs)
        if associated_properties:
            other_liens = get_other_liens(lien, lien.id)
            for ol in other_liens:
                if ol.date_paid is None:
                    total += Decimal(ol.foreclosure_costs)
                
    return total



def get_foreclosure_attorney_amount(lien_list, associated_properties = False):
    # Foreclosure Attorney Billing
    # Unpaid Bills
    
    total = 0

    for l in lien_list:
        lien = get_object_or_404(Lien, pk=int(l))
        total += Decimal(lien.attorney_foreclosure_expenses)
        if associated_properties:
            other_liens = get_other_liens(lien, lien.id)
            for ol in other_liens:
                if ol.date_paid is None:
                    total += Decimal(ol.attorney_foreclosure_expenses)
                
    return total

def get_other_costs_amount(lien_list, associated_properties = False):
    # Other Costs Incurred
    # Unpaid Bills
    
    total = 0

    for l in lien_list:
        lien = get_object_or_404(Lien, pk=int(l))
        total += Decimal(lien.pre_lit_charges)
        if associated_properties:
            other_liens = get_other_liens(lien, lien.id)
            for ol in other_liens:
                if ol.date_paid is None:
                    total += Decimal(ol.pre_lit_charges)
                
    return total


def get_admin_amount(lien_list, associated_properties = False):
    # Admin Fee
    # Unpaid Bills
    
    total = 0

    for l in lien_list:
        lien = get_object_or_404(Lien, pk=int(l))
        total += Decimal(lien.admin_fee)
        if associated_properties:
            other_liens = get_other_liens(lien, lien.id)
            for ol in other_liens:
                if ol.date_paid is None:
                    total += Decimal(ol.admin_fee)
                
    return total


def get_pre_lit_amount(lien_list, associated_properties = False):
    # Pre-lit Fee (KRS 134.452)
    # Unpaid Bills
    
    total = 0

    for l in lien_list:
        lien = get_object_or_404(Lien, pk=int(l))
        total += Decimal(lien.get_attorney_fee)
        if associated_properties:
            other_liens = get_other_liens(lien, lien.id)
            for ol in other_liens:
                if ol.date_paid is None:
                    total += Decimal(ol.get_attorney_fee)
                
    return total


def get_lit_amount(lien_list, associated_properties = False):
    # Litigation Costs
    # Unpaid Bills
    
    total = 0

    for l in lien_list:
        lien = get_object_or_404(Lien, pk=int(l))
        total += Decimal(lien.litigation_costs)
        if associated_properties:
            other_liens = get_other_liens(lien, lien.id)
            for ol in other_liens:
                if ol.date_paid is None:
                    total += Decimal(ol.litigation_costs)
                
    return total








# Reports Section

def get_write_off_mc_sale_data(lien_owner = None, start_date = None, end_date = None):

    before = start_date
    after = end_date

    writeOffLienIds = [];
    mcLienIds = [];
    lienIds = [];

    writeOffLienAmount = 0;
    writeOffLienCost = 0;
    writeOffLienActuallyPaid = 0;

    mcLienAmount = 0;
    mcLienCost = 0;
    mcActuallyPaid = 0;




    # Get writeoff liens - secondary status 42
    writeOffLiens = Lien.objects.filter(second_status = 42);

    # Mc sale second status id - 43
    mcLiens = Lien.objects.filter(second_status = 43);


    if before and after:
        writeOffLiens = writeOffLiens.filter(date_paid__range=(before, after));
        mcLiens = mcLiens.filter(date_paid__range=(before, after));

    for l in writeOffLiens:
        lienIds.append(int(l.id));
        writeOffLienIds.append(int(l.id));

        if l.actual_cost is None:
            l.actual_cost = 0;
        if l.actually_paid is None:
            l.actually_paid = 0;

        writeOffLienAmount = writeOffLienAmount + l.lien_amount;
        writeOffLienCost = l.actual_cost + writeOffLienCost;
        writeOffLienActuallyPaid = l.actually_paid + writeOffLienActuallyPaid;


    for ml in mcLiens:
        lienIds.append(int(ml.id));
        mcLienIds.append(int(ml.id));

        if ml.actual_cost is None:
            ml.actual_cost = 0;
        if ml.actually_paid is None:
            ml.actually_paid = 0;

        mcLienAmount = mcLienAmount + ml.lien_amount;
        mcLienCost = ml.actual_cost + mcLienCost;
        mcActuallyPaid = ml.actually_paid + mcActuallyPaid;

    mcCount = len(mcLienIds);
    writeOffCount = len(writeOffLienIds);

    data = {
        'write_off_ids' : writeOffLienIds, 'write_off_count' : writeOffCount, 'mc_count' : mcCount, 'lien_ids' : lienIds, 'before' : str(before), 'after' : str(after), 'writeOffLienAmount' : writeOffLienAmount, 'writeOffLienCost' : writeOffLienCost, 'writeOffLienActuallyPaid' : writeOffLienActuallyPaid, 'mcLienAmount' : mcLienAmount, 'mcLienCost' : mcLienCost, 'mcActuallyPaid' : mcActuallyPaid
    }

    return data









