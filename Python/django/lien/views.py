from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response, get_object_or_404, redirect, render
from django.http import HttpResponseRedirect, HttpResponse, Http404, StreamingHttpResponse
from django.template import TemplateDoesNotExist
from django.conf import settings
from django.contrib import messages

from datetime import *
from dateutil.relativedelta import *
from decimal import *
import csv, urllib, os
import simplejson

from lien.models import *
from lien.forms import *
from reporting.forms import *
from lien.reports import csv_payment_report, csv_attorney_billing_report

from lien.shortcuts import render_or_export, export_to_csv
from lien.utils import *
from utilities.letters import letterToProp, getLiensForLetter

import requests
from funcy import take
import json
from django.db.models import Q
import imgkit

from calendar import monthrange


from django.utils.encoding import smart_str

from reporting.utils import get_report_info
import time as real_time
from funcy import set_in

from cerberus import Validator
import pprint

from lien.admin_priv import *
from utilities.status_filters.forms import *
import utilities.status_filters.views as sf

import activity.views as activity

# @user_passes_test(lambda u: u.is_staff)
# def serve_export(request):
    
#     # Get date for filename
#     date = datetime.today().strftime('%Y-%m-%d');

#     filename = date +'.csv';

#     # Format of 2018-10-19 (October 19th 2018). Yes this is a time capsule
#     response = HttpResponse(mimetype='application/force-download')
#     response['Content-Disposition'] = 'attachment; filename=%s' % smart_str(filename)
#     response['X-Sendfile'] = smart_str('/media/short_exports/'+filename)
#     return response




@user_passes_test(lambda u: u.is_staff)
def purchased_from_report(self):
    jamos = Lien.objects.filter(purchased_from = 'JAMOS', purchased_from_new_id = 1);
    twin = Lien.objects.filter(purchased_from = 'Twinbrook LLC', purchased_from_new_id = 9);
    blueash = Lien.objects.filter(purchased_from = "Blue Ash", purchased_from_new_id = 6);
    detco = Lien.objects.filter(purchased_from = "Detco", purchased_from_new_id = 4);
    prov = Lien.objects.filter(purchased_from = "City of Providence", purchased_from_new_id = 7);
    hawes = Lien.objects.filter(purchased_from = "City of Hawesville", purchased_from_new_id = 8);
    dot = Lien.objects.filter(purchased_from = "DOT", purchased_from_new_id = 5);
    kyl = Lien.objects.filter(purchased_from = "KY LIEN HOLDINGS", purchased_from_new_id = 3);
    cc = Lien.objects.filter(purchased_from = 'COUNTY CLERK', purchased_from_new_id = 2);



    allelse = Lien.objects.filter(purchased_from = None, purchased_from_new_id = None, tax_year = 2013);



    return render_to_response('lien/purchased_from.html',{
    'jamos' : jamos,
    'twin' : twin,
    'blue' : blueash,
    'detco': detco,
    'prov' : prov,
    'hawes' : hawes,
    'dot' : dot,
    'kyl' : kyl,
    'allelse' : allelse,
    'cc': cc

    });


@user_passes_test(lambda u: u.is_staff)
def refund_request_report(request):

    lien_ids = [];
    liens = Lien.objects.filter(refund_requested = True);

    for l in liens:
        lien_ids.append(int(l.id));

    lienCount = liens.count();

    return render_to_response('lien/refund_request.html',{'liens': liens, 'lien_count': lienCount, 'lien_ids': lien_ids});


@user_passes_test(lambda u: u.is_staff)
def property_records_search_report(request):

    form = PropertyRecordsForm();
    lienIds = [];
    totalAmount = 0;
    

    # id  16

    if request.method == 'GET':
        form = PropertyRecordsForm(request.GET);

    before = '';
    after = '';
    county = '';

    if form.is_valid():

        before = form.cleaned_data['start_date'];
        after = form.cleaned_data['end_date'];

        county = form.cleaned_data['county'];


    expenses = Expense.objects.filter(expense_class_id = 16);
    expenses = expenses.filter(note__icontains="Property records search");
    expenses = expenses.filter(amount=95);

    if before and after:
        expenses = expenses.filter(expense_date__range=(before, after));

    if form.is_valid():
        if county:
            for e in expenses:
                lien = get_object_or_404(Lien, pk=int(e.lien_id));
                if county != lien.county:
                    expenses = expenses.exclude(id = int(e.id));

        
    for e in expenses:
        lien = get_object_or_404(Lien, pk=int(e.lien_id));
        
        # Make sure its only closed liens
        if lien.date_paid is not None:
            expenses = expenses.exclude(id = int(e.id));

    for e in expenses:
        lienIds.append(int(e.lien_id));
        totalAmount = totalAmount + int(e.amount);

    totalCount = len(lienIds);

    return render_to_response('lien/property_records_search_report.html', 
    {
        'form': form, 'lien_ids' : lienIds, 'before' : before, 'after' : after, 'county' : county, 'totalCount' : totalCount, 'totalAmount' : totalAmount
    }
    );
    
    


@user_passes_test(lambda u: u.is_staff)
def write_off_mc_report(request):

    form = McSaleWriteOffsForm();

    if request.method == 'GET':
        form = McSaleWriteOffsForm(request.GET);

    before = '';
    after = '';
    if form.is_valid():

        before = form.cleaned_data['start_date'];
        after = form.cleaned_data['end_date'];

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


    return render_to_response('lien/mc_sales_write_offs.html', 
    {
        'form': form, 'write_off_ids' : writeOffLienIds, 'write_off_count' : writeOffCount, 'mc_count' : mcCount, 'lien_ids' : lienIds, 'before' : before, 'after' : after, 'writeOffLienAmount' : writeOffLienAmount, 'writeOffLienCost' : writeOffLienCost, 'writeOffLienActuallyPaid' : writeOffLienActuallyPaid, 'mcLienAmount' : mcLienAmount, 'mcLienCost' : mcLienCost, 'mcActuallyPaid' : mcActuallyPaid
    });
    


@user_passes_test(lambda u: u.is_staff)
def status_info(request):
    status_info_form = StatusInfoForm()
    statusText = '';

    if request.method == 'GET':
        form = StatusInfoForm(request.GET);

    if form.is_valid():
        status = form.cleaned_data['status'];

        if status == 'any':
            liens = Lien.objects.filter(
                Q(assign_when_paid=True) | 
                Q(rep_by_atty=True)  |
                Q(structure_only=True)  |
                Q(refund_in_progress=True)  |
                Q(dnb=True) 
            );
            statusText = 'Any';
        elif status == 'assign_when_paid':
            liens = Lien.objects.filter(assign_when_paid=True);
            statusText = 'Assign When Paid';
        elif status == 'rep_by_atty':
            liens = Lien.objects.filter(rep_by_atty=True);
            statusText = 'Rep By Atty';
        elif status == 'structure_only':
            liens = Lien.objects.filter(structure_only=True);
            statusText = 'Structure Only';
        elif status == 'refund_in_progress':
            liens = Lien.objects.filter(refund_in_progress=True);
            statusText = 'Refund In Progress';
        elif status == 'dnb':
            liens = Lien.objects.filter(dnb=True);
            statusText = 'DNB';
    else:
        # Show all
        liens = Lien.objects.filter(
                Q(assign_when_paid=True) | 
                Q(rep_by_atty=True)  |
                Q(structure_only=True)  |
                Q(refund_in_progress=True)  |
                Q(dnb=True) 
            );
        statusText = 'Any';


    return render_to_response('lien/status_info.html',{'liens': liens, 'status_info_form': status_info_form, 'statusText' : statusText})

        





@user_passes_test(lambda u: u.is_staff)
def view_unpaid_bills(request):
    unpaid_form = UnpaidBillsForm()

    if request.method == 'GET':
        form = UnpaidBillsForm(request.GET);


    if form.is_valid():

        beforeDate = form.cleaned_data['unpaid_date_before'];
        afterDate = form.cleaned_data['unpaid_date_after'];

        # Excluding payments, notes and expenses within the date range too
        paymentList = [];
        noteList = [];
        expenseList = [];

        # This didnt work below. Why? i dont know. Too time pressed to care
        
        # liens = Lien.objects.filter(
        # ~Q(date_first_letter__range=(beforeDate, afterDate)) | 
        # ~Q(date_second_letter__range=(beforeDate, afterDate)) 
        # ~Q(date_third_letter__range=(beforeDate, afterDate)) |
        # ~Q(date_fourth_letter__range=(beforeDate, afterDate)) |
        # ~Q(foreclosure_warning_letter__range=(beforeDate, afterDate)) |
        # ~Q(date_occupant_letter__range=(beforeDate, afterDate))|
        # ~Q(updated_at__range=(beforeDate, afterDate))
        # );


        # Get bills that are unpaid with a letter sent between the Date Range of User Input
        liens = Lien.objects.filter(~Q(date_first_letter__range=(beforeDate, afterDate)));
        liens = liens.filter(~Q(date_second_letter__range=(beforeDate, afterDate)));
        liens = liens.filter(~Q(date_third_letter__range=(beforeDate, afterDate)));
        liens = liens.filter(~Q(date_fourth_letter__range=(beforeDate, afterDate)));
        liens = liens.filter(~Q(foreclosure_warning_letter__range=(beforeDate, afterDate)));
        liens = liens.filter(~Q(date_occupant_letter__range=(beforeDate, afterDate)));
        liens = liens.filter(~Q(updated_at__range=(beforeDate, afterDate)));

         # Get list of payments within the range
        payments = Payment.objects.filter(date__range=(beforeDate, afterDate));
        for p in payments:
            paymentList.append(p.lien_id);

        # Note list
        notes = Note.objects.filter(created_at__range=(beforeDate, afterDate));
        for n in notes:
            noteList.append(n.lien_id);

        # Expense list
        expenses = Expense.objects.filter(expense_date__range=(beforeDate, afterDate));
        for e in expenses:
            expenseList.append(e.lien_id);


        liens = liens.exclude(id__in=(paymentList));
        liens = liens.exclude(id__in=(noteList));
        liens = liens.exclude(id__in=(expenseList));
        liens = liens.filter(date_paid__isnull = True);

        unique = get_unique_properties(liens);
        

        return render_to_response('lien/view_unpaid_bills.html', {'unique' : unique, 'lienCount' : liens.count(), 'liens' : liens, 'beforeDate': beforeDate, 'afterDate' : afterDate, 'unpaid_form' : unpaid_form})

    else:
        return HttpResponseRedirect(reverse('lien-index'))


def get_unique_properties(liens):
    liens = liens.order_by('map_number').values('map_number', 'county').distinct();

    return liens.count();


@user_passes_test(lambda u: u.is_staff)
def view_foreclosures(request):


    # id 27 = foreclosure
    # id 12 = litigation
    if request.method == 'GET':
        form = ForeclosureForm(request.GET)

    if form.is_valid():
        investor = '';
        county = '';
        # liens = Lien.objects.filter( | Q(second_status_id = 12) | Q(second_status_id = 27) | Q(third_status_id = 12) | Q(third_status_id = 27))

        # First Status required as foreclosure... maybe 3rd?
        liens = Lien.objects.filter(Q (status_id = 12) | Q(status_id = 27))

        # Filter by county if value selected
        if form.cleaned_data['county']:
            liens = liens.filter(county = form.cleaned_data['county'])
            county = form.cleaned_data['county'];

        # Filter by investor is value selected
        if form.cleaned_data['investor']:
            liens = liens.filter(investor = form.cleaned_data['investor'])
            investor = form.cleaned_data['investor'];



   

        return render_to_response('lien/view_foreclosures.html',{'liens': liens, 'county': county, 'investor': investor})
    else:
        return HttpResponseRedirect(reverse('lien-index'))


@user_passes_test(lambda u: u.is_staff)
def search(request):
    """
    Search view for the searching liens

    Template - lien/search.html
        liens - list of liens found in search
        query - url encoded query from search

    Uses `render_or_export` wrapper
    """
    if request.method == 'GET':
        form = SearchForm(request.GET)
        if form.is_valid():

            liens = Lien.objects.search(form.cleaned_data['keywords'])

            if form.cleaned_data['county']:
                newLiens = [];
                for lien in liens:
                    if lien.county == form.cleaned_data['county']:
                        newLiens.append(lien);


            # If there is only one result, send them to that lien
            if form.cleaned_data['county']:
                if len(liens) == 1:
                    return HttpResponseRedirect(reverse('lien-view', args = [newLiens[0].id]))
            else:
                if len(liens) == 1:
                    return HttpResponseRedirect(reverse('lien-view', args = [liens[0].id]))

            # This query var allows for linking back to the search
            # and linking to the export view
            query = urllib.urlencode(request.GET)
            if form.cleaned_data['county']:
                return render_or_export('lien/search.html', {'liens': newLiens, 'query': query}, request)
            else:
                return render_or_export('lien/search.html', {'liens': liens, 'query': query}, request)
    else:
        return HttpResponseRedirect(reverse('lien-index'))

@user_passes_test(lambda u: u.is_staff)
def expense_search(request):
    '''
    Expense Search Section

    '''
    if request.method == 'GET':
        form = ExpenseSearchForm(request.GET)

        if form.is_valid():
            expense_class = form.cleaned_data['expense_class']
            expense_attorney = form.cleaned_data['expense_attorney']
            expense_note = form.cleaned_data['expense_note']
            expense_amount = form.cleaned_data['expense_amount']
            
            expenses = Expense.objects.all()

            KEYS = [( 'expense_class',expense_class ), ( 'attorney', expense_attorney ), ( 'note', expense_note )]

            if expense_class:
                expenses = expenses.filter(expense_class=expense_class)
            if expense_attorney:
                expenses = expenses.filter(attorney=expense_attorney)
            if expense_note:
                expenses = expenses.filter(note__icontains=expense_note)
            if expense_amount:
                expenses = expenses.filter(amount=expense_amount)
            query = urllib.urlencode(request.GET)

            return render_or_export('lien/search.html', {'expenses': expenses, 'query': query, 'total_count': len(expenses)}, request)
        else:
            return HttpResponseRedirect(reverse('lien-index'))
    else:
        return HttpResponseRedirect(reverse('lien-index'))

@user_passes_test(lambda u: u.is_staff)
def date_search(request):
    """
    Date search view for filtering down liens

    Template - lien/search.html
        liens - list of liens found in search
        query - url encoded query from search

    Uses `render_or_export` wrapper
    """
    if request.method == 'GET':
        form = DateSearchForm(request.GET)

        if form.is_valid():
            if not form.cleaned_data['from_date'] or not form.cleaned_data['to_date']:
                if form.cleaned_data['date_field'] != 'no_date':
                    liens = Lien.objects.filter(**{
                        '%s__isnull' % form.cleaned_data['date_field']: True,
                    })
                else:
                    liens = Lien.objects.all()
            else:
                liens = Lien.objects.date_search(form.cleaned_data['from_date'], form.cleaned_data['to_date'],
                                                 form.cleaned_data['date_field'])
            if form.cleaned_data['investor']:
                liens = liens.filter(investor=form.cleaned_data['investor'])

            if form.cleaned_data['county']:
                liens = liens.filter(county=form.cleaned_data['county'])

            if form.cleaned_data['status']:
                liens = liens.filter(status=form.cleaned_data['status'])

            if form.cleaned_data['second_status']:
                liens = liens.filter(second_status=form.cleaned_data['second_status'])

            if form.cleaned_data['third_status']:
                liens = liens.filter(third_status=form.cleaned_data['third_status'])

            if form.cleaned_data['paid_status'] == 'paid':
                liens = liens.filter(date_paid__isnull=False)
            elif form.cleaned_data['paid_status'] == 'unpaid':
                liens = liens.filter(date_paid__isnull=True)

            if form.cleaned_data['action_date']:
                liens = liens.filter(action_date=form.cleaned_data['action_date'])

            if form.cleaned_data['lien_owner']:
                liens = liens.filter(lien_owner=form.cleaned_data['lien_owner'])

            if form.cleaned_data['purchased_from']:
                liens = liens.filter(purchased_from_new=form.cleaned_data['purchased_from'])

            if form.cleaned_data['tax_year'] != 'any':
                liens = liens.filter(tax_year=int(form.cleaned_data['tax_year']))

            if form.cleaned_data['attorney']:
                liens = liens.filter(attorney_id=form.cleaned_data['attorney'])

            if form.cleaned_data['ci_number']:
                ci_number = form.cleaned_data['ci_number'];
               

                liens = liens.filter(
                    case_number__icontains = ci_number
                )
                

                if liens.count() == 0:
                    if 'CI' not in ci_number and 'ci' not in ci_number:
                        ci_number = 'CI-' + ci_number;
                    # Search the notes, excluding liens from above
                    liens = liens.filter(
                        Q(note__body__icontains=ci_number)
                    )

            if form.cleaned_data['street_address']:
                street_address = form.cleaned_data['street_address']
                liens = liens.filter(
                    Q(owner_address__icontains=street_address) | \
                    Q(owner_address2__icontains=street_address) | \
                    Q(current_owner_address__icontains=street_address) | \
                    Q(current_owner_address2__icontains=street_address) | \
                    Q(property_location__icontains=street_address)
                )

            if form.cleaned_data['current_owner']:
                current_owner = form.cleaned_data['current_owner']
                liens = liens.filter(current_owner_name__icontains=current_owner)

            # If there is only one result, redirect to that result
            #if len(liens) == 1:
            #    return HttpResponseRedirect(reverse('lien-view', args = [liens[0].id]))

            query = urllib.urlencode(request.GET)

            return render_or_export('lien/search.html', {'liens': liens, 'query': query, 'total_count': len(liens)}, request)
        else:
            return HttpResponseRedirect(reverse('lien-index'))
    else:
        return HttpResponseRedirect(reverse('lien-index'))

@user_passes_test(lambda u: u.is_staff)
def payment_report(request):
    """
    Payment report

    Uses the `PaymentReportForm`

    Returns a CSV
    """
    form = PaymentReportForm(request.POST)

    if form.is_valid():
        end   = form.cleaned_data['end_date']
        start = form.cleaned_data['start_date']
        payments = Payment.objects.filter(date__gte=form.cleaned_data['start_date'],
                                          date__lte=form.cleaned_data['end_date'])

        response = StreamingHttpResponse(
                csv_payment_report.stream(start=start, end=end),
                content_type="text/csv"
            )
        response['Content-Disposition'] = 'attachment; filename=payment_report.csv'
        return response
    else:
        return HttpResponseRedirect(reverse('lien-index'))


@user_passes_test(lambda u: u.is_staff)
def attorney_billing_report(request):
    """
    Payment report

    Uses the `PaymentReportForm`

    Returns a CSV
    """
    form = AttorneyBillingReportForm(request.POST)

    if form.is_valid():
        end   = form.cleaned_data['end_date']
        start = form.cleaned_data['start_date']
        payments = Payment.objects.filter(date__gte=form.cleaned_data['start_date'],
                                          date__lte=form.cleaned_data['end_date'])

        response = StreamingHttpResponse(
                csv_attorney_billing_report.stream(start=start, end=end),
                content_type="text/csv"
            )
        response['Content-Disposition'] = 'attachment; filename=payment_report.csv'
        return response
    else:
        return HttpResponseRedirect(reverse('lien-index'))

@user_passes_test(lambda u: u.is_staff)
def release_report_view(request, id):
    """
    Release report view

    Args:
        id - This is the id of the County being looked at

    Template - lien/releaes_report_view.html
        liens - All liens released last month
        county - County being looked at

    Uses `render_or_export` wrapper
    """
    county = County.objects.get(pk=id)
    liens = Lien.objects.released_last_month().filter(county__id=id)
    return render_or_export('lien/release_report_view.html', {'liens': liens, 'county': county}, request)

@user_passes_test(lambda u: u.is_staff)
def release_report_index(request):
    """
    Release report index page for displaying county list

    Template - lien/release_report_index.html
        counties - List of all counties
    """
    counties = County.objects.all()
    return render_to_response('lien/release_report_index.html', {'counties': counties})

@user_passes_test(lambda u: u.is_staff)
def day_one_report_view(request, id):
    """
    Report for showing liens purchased in a county yesterday

    Args:
        id - This is the id of the County being looked at

    Template - lien/day_one_report_view.html
        liens - All liens released last month
        county - County being looked at

    Uses `render_or_export` wrapper
    """
    county = County.objects.get(pk=id)
    liens = Lien.objects.purchased_yesterday().filter(county__id=id)
    return render_or_export('lien/day_one_report_view.html', {'liens': liens, 'county': county}, request)

@user_passes_test(lambda u: u.is_staff)
def day_one_report_index(request):
    """
    Day one report index for listing counties

    Template - lien/day_one_report_index.html
        counties - List of all counties
    """
    counties = County.objects.all()
    return render_to_response('lien/day_one_report_index.html', {'counties': counties})

@user_passes_test(lambda u: u.is_staff)
def foreclosure_report(request):
    """
    CSV Export for foreclosure report

    Returns CSV file
    """
    liens = Lien.objects.filter(foreclosure_date__isnull=False, date_paid__isnull=True)
    return export_to_csv(liens)

def annual_notice_report(request):
    liens = Lien.objects.filter(date_first_letter__isnull=False,
                                foreclosure_warning_letter__isnull=True,
                                date_paid__isnull=True)
    liens = liens.extra(
        where=['DATE_ADD(lien_lien.date_first_letter, INTERVAL 11 MONTH) < DATE(NOW())']
    )

    query = urllib.urlencode(request.GET)

    return render_or_export('lien/search.html', {'liens': liens, 'query': query}, request)


def get_data(id, lien):
    # JSON to get Ipad data
    r = requests.get("https://argfox-test.ventretech.com/inspection-acct/"+id);

    # r = requests.get("https://argfox.ventretech.com/inspection-acct/"+id);

    isAssociated = False
    earliestLien = lien

    # This is last ditch effort to get the associated liens and see if images exists
    if not r.json():
        earliestLien = get_associated_lien_with_earliest_tax_year(lien, id)
        newR = r

        if earliestLien:

            # argfox-test.ventre.tech
            # newR = requests.get("https://argfox.ventretech.com/inspection-acct/"+str(earliestLien.id))
            
            newR = requests.get("https://argfox-test.ventretech.com/inspection-acct/"+str(earliestLien.id))

        if newR.json():
            r = newR

            
            isAssociated = True

    # Convert it to json
    list_dict = r.json();

    # initialize data for template
    pictures = [];
    notes = [];
    data_dict = {};


    

    # if the dictionary exists
    if(list_dict):
        pictures = list_dict[0]['pictures'];
        notes = list_dict[0]['answers'][24]['value'];
        # ipad worksheet

       
        for d in list_dict[0]['answers']:
            if type(d['value']) is list:
                if(d['value']):
                    data_dict[d['label']] = d['value'][0];
            else:
                data_dict[d['label']] = d['value'];



    was = '<input type="checkbox">'
    newIs = '<input type="checkbox" checked>'



    # STARTING OPTIONS

    # Occupied
    occupied = """
            <p>
                <input type="checkbox">
                Occupied
            </p>
        """

    vacant = """
            <p>
                <input type="checkbox">
                Vacant
            </p>
        """



    # Property Type
    ptRes = """
                <p>
                    <input type="checkbox">
                    Resdential
                </p>
            """

    ptComm = """
            <p>
                <input type="checkbox">
                Commercial
            </p>
            """

    ptInd = """
            <p>
                <input type="checkbox">
                Industrial
            </p>
        """


    ptFarm = """
            <p>
                <input type="checkbox">
                Farm
            </p>
        """

    # Structure Type
    stHouse = """
            <p>
                <input type="checkbox">
                House
            </p>
             """
    stMobile = """
            <p>
                <input type="checkbox">
                Mobile Home
            </p>
            """

    st1uble = """
            <p>
                <input type="checkbox">
                Doublewide
            </p>
            """

    stModular = """
            <p>
                <input type="checkbox">
                Modular
            </p>
            """

    stOther = """
            <p>
                <input type="checkbox">
                Other
            </p>
            """

    # of Stories
    oneStory = """
            <p>
                <input type="checkbox">
                1
            </p>
            """

    twoStory = """
            <p>
                <input type="checkbox">
                2
            </p>
            """

    threeStory = """
            <p>
                <input type="checkbox">
                3
            </p>
            """

    moreStory = """
            <p>
                <input type="checkbox">
                More
            </p>
            """

    # Utilities
    electric = """
            <p>
                <input type="checkbox">
                Electric
            </p>
            """
    gas = """
            <p>
                <input type="checkbox">
                Gas
            </p>
            """
    water = """
            <p>
                <input type="checkbox">
                Water
            </p>
            """
    phone = """
            <p>
                <input type="checkbox">
                Phone
            </p>
            """
    sewer = """
            <p>
                <input type="checkbox">
                Sewer
            </p>
            """
    unknown = """
            <p>
                <input type="checkbox">
                Unknown
            </p>
            """
    # Structure Cnndition
    scExcellent = """
            <p>
                <input type="checkbox">
                Excellent
            </p>
            """
    scGood = """
            <p>
                <input type="checkbox">
                Good
            </p>
            """
    scFair= """
            <p>
                <input type="checkbox">
                Fair
            </p>
            """

    scPoor = """
            <p>
                <input type="checkbox">
                Poor
            </p>
            """
    scUnlivable = """
            <p>
                <input type="checkbox">
                Unlivable
            </p>
            """
    #Siding
    brick = """
            <p>
                <input type="checkbox">
                Brick
            </p>
            """
    wood = """
            <p>
                <input type="checkbox">
                Wood
            </p>
            """
    metal = """
            <p>
                <input type="checkbox">
                Metal
            </p>
            """
    vinyl = """
            <p>
                <input type="checkbox">
                Vinyl
            </p>
            """
    concrete = """
            <p>
                <input type="checkbox">
                Concrete
            </p>
            """

    # Roof
    roofGood = """
            <p>
                <input type="checkbox">
                Good
            </p>
            """
    roofFair= """
            <p>
                <input type="checkbox">
                Fair
            </p>
            """

    roofPoor = """
            <p>
                <input type="checkbox">
                Poor
            </p>
            """
    roofUnknown = """
            <p>
                <input type="checkbox">
                Unknown
            </p>
            """
    # DriveWay
    driveAsphalt = """
            <p>
                <input type="checkbox">
                Asphalt
            </p>
            """

    driveConcrete = """
            <p>
                <input type="checkbox">
                Concrete
            </p>
            """

    driveGravel = """
            <p>
                <input type="checkbox">
                Gravel
            </p>
            """
    # Neighborhood
    nExcellent = """
            <p>
                <input type="checkbox">
                Excellent
            </p>
            """
    nGood = """
            <p>
                <input type="checkbox">
                Good
            </p>
            """
    nFair= """
            <p>
                <input type="checkbox">
                Fair
            </p>
            """

    nPoor = """
            <p>
                <input type="checkbox">
                Poor
            </p>
            """
    # Garage
    attached = """
            <p>
                <input type="checkbox">
                Attached
            </p>
            """
    unattached = """
            <p>
                <input type="checkbox">
                Unattached
            </p>
            """
    garageNone = """
            <p>
                <input type="checkbox">
                None
            </p>
            """
    # Garage Condition
    gExcellent = """
            <p>
                <input type="checkbox">
                Excellent
            </p>
            """
    gGood = """
            <p>
                <input type="checkbox">
                Good
            </p>
            """
    gFair= """
            <p>
                <input type="checkbox">
                Fair
            </p>
            """

    gPoor = """
            <p>
                <input type="checkbox">
                Poor
            </p>
            """
    gNA = """
            <p>
                <input type="checkbox">
                N/A
            </p>
            """
    # Other Buildings
    otherYes = """
            <p>
                <input type="checkbox">
                Yes
            </p>
            """
    otherNo = """
            <p>
                <input type="checkbox">
                No
            </p>
            """
    # Lot Conditions
    lotGood = """
            <p>
                <input type="checkbox">
                Good
            </p>
            """
    lotFair= """
            <p>
                <input type="checkbox">
                Fair
            </p>
            """

    lotPoor = """
            <p>
                <input type="checkbox">
                Poor
            </p>
            """
    # Pool
    inGround = """
            <p>
                <input type="checkbox">
                In Ground
            </p>
            """
    aboveGround = """
            <p>
                <input type="checkbox">
                Above Ground
            </p>
            """
    poolNone = """
            <p>
                <input type="checkbox">
                None
            </p>
            """
    # Sidewalk
    sidewalkYes = """
            <p>
                <input type="checkbox">
                Yes
            </p>
            """
    sidewalkNo = """
            <p>
                <input type="checkbox">
                No
            </p>
            """

    # Offstreet Parking
    parkingYes = """
            <p>
                <input type="checkbox">
                Yes
            </p>
            """
    parkingNo = """
            <p>
                <input type="checkbox">
                No
            </p>
            """
    # Lighted Streets
    lightedYes = """
            <p>
                <input type="checkbox">
                Yes
            </p>
            """
    lightedNo = """
            <p>
                <input type="checkbox">
                No
            </p>
            """
    # Use consistent with neighboorhood
    neighborYes = """
            <p>
                <input type="checkbox">
                Yes
            </p>
            """
    neighborNo = """
            <p>
                <input type="checkbox">
                No
            </p>
            """

    # Acreage
    default_unchecked_box_template = """
           <p>
                 <input type="checkbox">
                 {{ answer }}
           </p>
    """
    def get_checkbox(answer, checked):
        checked_str = "checked" if checked else ""
        template = """
          <p>
            <input type="checkbox" {0} />
                {1}
          </p>
        """.format(checked_str, answer)
        return template




    accountNumber = 0;
    address = '';
    comments = "";
    acreageAnsw = "Not provided"
    stDouble = '';


    for key, value in data_dict.iteritems():

        if(key == "Account #" or key == "Id #"):
            accountNumber = value;

        if(key == "Street Address"):
            address = value;

        if(key == "City"):
            address = address + ", "+value;

        if(key == "County"):
            address = address + ","+value+" County,";

        # TODO:: FIX THIS
        if(key == "State"):
            address = address + ", "+str(value);


        if(key == "Occupied?"):
            if (value == "occupied"):
                occupied = occupied.replace(was, newIs);
            if (value == "vacant"):
                vacant = vacant.replace(was, newIs);

        
        if(key == "Property Type"):
            if (value == "residential"):
                ptRes = ptRes.replace(was, newIs);
            if (value == "commercial"):
                ptComm = ptComm.replace(was, newIs);
            if (value == "industrial"):
                ptInd = ptInd.replace(was, newIs);
            if (value == "farm"):
                ptFarm = ptFarm.replace(was, newIs);

        if(key == "Type of Structure"):
            if (value == "house"):
                stHouse = stHouse.replace(was, newIs);
            if (value == "mobile home"):
                stMobile = stMobile.replace(was, newIs);
            if (value == "doublewide"):
                stDouble = stDouble.replace(was, newIs);
            if (value == "modular"):
                stModular = stModular.replace(was, newIs);
            if (value == "other"):
                stOther = stOther.replace(was, newIs);

        if(key == "Number of stories"):
            if str(value) == '1':
                oneStory = oneStory.replace(was, newIs);
            if str(value) == '2':
                twoStory = twoStory.replace(was, newIs);
            if str(value) == '3':
                threeStory = threeStory.replace(was, newIs);
            if str(value) == 'more':
                moreStory = moreStory.replace(was, newIs);

        if(key == "Utilities"):
            if value == "electric":
                electric = electric.replace(was, newIs);
            if value == "gas":
                gas = gas.replace(was, newIs);
            if value == "water":
                water = water.replace(was, newIs);
            if value == "phone":
                phone = phone.replace(was, newIs);
            if value == "sewer":
                sewer = sewer.replace(was, newIs);
            if value == "unknown":
                unknown = unknown.replace(was, newIs);
        
        if(key == "Structure Condition"):
            if value =="excellent":
                scExcellent = scExcellent.replace(was, newIs);
            if value =="good":
                scGood = scGood.replace(was, newIs);
            if value =="fair":
                scFair= scFair.replace(was, newIs);
            if value =="poor":
                scPoor = scPoor.replace(was, newIs);
            if value =="unlivable":
                scUnlivable = scUnlivable.replace(was, newIs);

        if(key == "Siding"):
            if value == "brick":
                brick = brick.replace(was, newIs);
            if value == "wood":
                wood = wood.replace(was, newIs);
            if value == "metal":
                metal = metal.replace(was, newIs);
            if value == "vinyl":
                vinyl = vinyl.replace(was, newIs);
            if value == "concrete":
                concrete = concrete.replace(was, newIs);
            
        
        if(key == "Roof"):
            if value =="good":
                roofGood = roofGood.replace(was, newIs);
            if value =="fair":
                roofFair= roofFair.replace(was, newIs);
            if value =="poor":
                roofPoor = roofPoor.replace(was, newIs);
            if value =="unknown":
                roofUnknown = roofUnknown.replace(was, newIs);

        if(key == "Driveway"):
            if value == "asphalt":
                driveAsphalt = driveAsphalt.replace(was, newIs);
            if value == "concrete":
                driveConcrete = driveConcrete.replace(was, newIs);
            if value == "gravel":
                driveGravel = driveGravel.replace(was, newIs);


        if(key == "Neighborhood"):
            if value =="excellent":
                nExcellent = nExcellent.replace(was, newIs);
            if value =="good":
                nGood = nGood.replace(was, newIs);
            if value =="fair":
                nFair= nFair.replace(was, newIs);
            if value =="poor":
                nPoor = nPoor.replace(was, newIs);

        
        if(key == "Garage"):
            if value == "attached":
                attached = attached.replace(was, newIs);
            if value == "unattached":
                unattached = unattached.replace(was, newIs);
            if value == "none":
                garageNone = garageNone.replace(was, newIs);

        if(key == "Garage Condition"):
            if value =="excellent":
                gExcellent = gExcellent.replace(was, newIs);
            if value =="good":
                gGood = gGood.replace(was, newIs);
            if value =="fair":
                gFair= gFair.replace(was, newIs);
            if value =="poor":
                gPoor = gPoor.replace(was, newIs);
            if value =="N/A":
                gNA = gNA.replace(was, newIs);

        if(key == "Other buildings"):
            if value == "yes":
                otherYes = otherYes.replace(was, newIs);
            if value == "no":
                otherNo = otherNo.replace(was, newIs);

        if(key == "Lot conditions"):
            if value == "good":
                lotGood = lotGood.replace(was, newIs);
            if value == "fair":
                lotFair= lotFair.replace(was, newIs);
            if value =="poor":
                lotPoor = lotPoor.replace(was, newIs);


        if(key == "Pool"):
            if value == "in ground":
                inGround = inGround.replace(was, newis);
            if value == "above ground":
                aboveGround = aboveGround.replace(was, newIs);
            if value == "none":
                poolNone = poolNone.replace(was, newIs);

        if(key == "Sidwalks"):
            if value == "yes":
                sidewalkYes = sidewalkYes.replace(was, newIs);
            if value == "no":
                sidewalkNo = sidewalkNo.replace(was, newIs);

        if(key == "Off Street Parking"):
            if value == "yes":
                parkingYes = parkingYes.replace(was, newIs);
            if value == "no":
                parkingNo = parkingNo.replace(was, newIs);

        if(key == "Lighted Streets"):
            if value == "yes":
                lightedYes = lightedYes.replace(was, newIs);
            if value == "no":
                lightedNo = lightedNo.replace(was, newIs);
        if(key == "Use consistent with neighborhood?"):
            if value == "yes":
                neighborYes = neighborYes.replace(was, newIs);
            if value == "no":
                neighborNo = neighborNo.replace(was, newIs);


        if(key == "Comments"):
            comments = value;

        if key.lower() == 'acreage':
            acreageAnsw = value


    options = {
        "xvfb": ""
    }

    # img = imgkit.from_url('http://google.com', False, options = options)

    body = """
<div class="container_12">
        <div class="grid_12">
            

            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                <h6>Property Info</h6>
                <p>
                ID 
                %s
                </p>
                <p>
                    %s
                </p>
            </div>

            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                <p>
                    %s
                    %s
                </p>
            </div>


            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                <h6>Property Type</h6>
                    <p>
                        %s
                        %s
                        %s
                        %s
                    </p>
            </div>




            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                <h6>Type of Structure</h6>
                <p>
                        
                        %s
                        %s
                        %s
                        %s
                        %s
                </p>
                <p>
                    Specify:
                    <br />
                </p>
            </div>



            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                <h6>Number of Stories</h6>
                <p>
                        %s
                        %s
                        %s
                        %s
                </p>
            </div>

            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                <h6>Utilities</h6>
                <p>
                    %s
                    %s
                    %s
                    %s
                    %s
                    %s
                </p>
            </div>


            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                    <h6>Structure Condition</h6>
                    <p>
                        %s
                        %s
                        %s
                        %s
                        %s
                    </p>
            </div>

            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                    <h6>Siding</h6>
                    <p>
                        %s
                        %s
                        %s
                        %s
                        %s
                    </p>
            </div>

            
            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                    <h6>Roof</h6>
                    <p>
                        %s
                        %s
                        %s
                        %s
                    </p>
            </div>

            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                    <h6>Driveway</h6>
                    <p>
                        %s
                        %s
                        %s
                    </p>
            </div>

            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                    <h6>Neighborhood</h6>
                    <p>
                        %s
                        %s
                        %s
                        %s
                    </p>
            </div>


            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 270px;">
                    <h6>Garage</h6>
                    <p>
                        %s
                        %s
                        %s
                    </p>
            </div>


            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 230px;">
                    <h6>Garage Condition</h6>
                    <p>
                        %s
                        %s
                        %s
                        %s
                        %s
                    </p>
            </div>

            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 230px;">
                    <h6>Other Buildings</h6>
                    <p>
                        %s
                        %s
                    </p>
            </div>

            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; height: 230px;">
                    <h6>Lot Condition</h6>
                    <p>
                        %s
                        %s
                        %s
                    </p>
            </div>


            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; max-height: 999px; height: 230px;">
                    <h6>Pool</h6>
                    <p>
                        %s
                        %s
                        %s
                    </p>
            </div>



            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; max-height: 999px; height: 150px;">
                    <h6>Sidewalks</h6>
                    <p>
                        %s
                        %s
                    </p>
            </div>

            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; max-height: 999px; height: 150px;">
                    <h6>Off Street Parking</h6>
                    <p>
                        %s
                        %s
                    </p>
            </div>

            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; max-height: 999px; height: 150px;">
                    <h6>Lighted Streets</h6>
                    <p>
                        %s
                        %s
                    </p>
            </div>

            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; max-height: 999px; height: 150px;">
                    <h6>Use consistent with Neighborhood</h6>
                    <p>
                        %s
                        %s
                    </p>
            </div>
            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; max-height: 999px; height: 150px;">
                    <h6>Acreage</h6>
                    <p>
                    %s

                    </p>
            </div>
            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; max-height: 999px; height: 150px;">
            </div>
            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; max-height: 999px; height: 150px;">
            </div>
            <div class="grid_3" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; max-height: 999px; height: 150px;">
            </div>

            <div class="grid_12" style="border-style: solid; border-width: 1px; margin-left: 0; margin-right: 0; max-height: 999px; height: 150px; max-width: 999px; width: 885px">
                    <h6>Comments</h6>
                    <p>
                    %s

                    </p>
            </div>
    </div>
    """ % (accountNumber, address, occupied, vacant, ptRes, ptComm, ptInd, ptFarm, stHouse, stMobile, stDouble, stModular, stOther, 
           oneStory, twoStory, threeStory, moreStory, electric, gas, water, phone, sewer, unknown, scExcellent, scGood, scFair, scPoor, scUnlivable, brick, wood, metal, vinyl, concrete, roofGood, roofFair, roofPoor, roofUnknown, driveAsphalt, driveConcrete, driveGravel, nExcellent, nGood, nFair, nPoor, attached, unattached, garageNone, gExcellent, gGood, gFair, gPoor, gNA, otherYes, otherNo, lotGood, lotFair, lotPoor, inGround, aboveGround, poolNone, sidewalkYes, sidewalkNo, parkingYes, parkingNo, lightedYes, lightedNo, neighborYes, neighborNo, acreageAnsw, comments)
    
    
    # CSS files for the html string
    css = [
        'liendata/assets/css/reset.css',
        'liendata/assets/css/text.css',
        'liendata/assets/css/960.css',
        'liendata/assets/css/screen.css',
    ]

    # If the directory doesnt exist with that lien id- create it for the imgkit to save the image
    if not os.path.exists("liendata/assets/worksheet/"+str(id)):
        os.makedirs("liendata/assets/worksheet/"+str(id))

    img = imgkit.from_string(body, "liendata/assets/worksheet/"+str(id)+"/out.png", options = options, css = css)

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


    thirdPartyTotal = 0;

    governmentTotal = 0;
    governmentTotals = {};

    bankTotals = {};
    bankTotal = 0;
    
    otherTotal = 0;
    otherTotals = {};

    grandTotal = 0;
    lienGrandTotal = 0;
    interestGrandTotal = 0;
    adminGrandTotal = 0;
    litCostGrandTotal = 0;
    preLitGrandTotal = 0;
    litExpenseGrandTotal = 0;
    amountRequestedGrandTotal = 0;
    i = 0;
    amount = 0;

    for lien_holder in lien.lienholder_set.all():
        governmentTotal = 0;
        bankTotal = 0;
        if lien.lien_amount is None:
            lien.lien_amount = 0;
        elif lien.total_interest is None:
            lien.total_interest = 0;
        elif lien.admin_fee is None:
            lien.admin_fee = 0;
        elif lien.litigation_costs is None:
            lien.litigation_costs = 0;
        elif lien.litigation_expenses is None:
            lien.litigation_expenses = 0;
        elif lien.attorney_expenses is None:
            lien.attorney_expenses = 0;
            
        if lien_holder.category == "3rd party":
            thirdPartyTotal = lien.lien_amount + lien.total_interest + lien.admin_fee + lien.litigation_costs + lien.litigation_expenses + lien.attorney_expenses;
            setattr(lien, 'rowTotal', thirdPartyTotal)
            grandTotal += thirdPartyTotal;
            lienGrandTotal += lien.lien_amount;
            interestGrandTotal += lien.total_interest;
            adminGrandTotal += lien.admin_fee;
            litCostGrandTotal += lien.litigation_costs;
            preLitGrandTotal += lien.attorney_expenses;
            litExpenseGrandTotal += lien.litigation_expenses;




            

        if lien_holder.category == "government":
            if lien_holder.lien_holder_face_amount == None:
                lien_holder.lien_holder_face_amount = 0;
                governmentTotal += lien_holder.lien_holder_face_amount;

                lienGrandTotal += lien_holder.lien_holder_face_amount;
            else:
                governmentTotal += lien_holder.lien_holder_face_amount;
                lienGrandTotal += lien_holder.lien_holder_face_amount;

            if lien_holder.lien_holder_interest_amount == None:
                lien_holder.lien_holder_interest_amount = 0;
                governmentTotal += lien_holder.lien_holder_interest_amount;

                interestGrandTotal += lien_holder.lien_holder_interest_amount;
            else:
                governmentTotal += lien_holder.lien_holder_interest_amount;
                interestGrandTotal += lien_holder.lien_holder_interest_amount;

            if lien_holder.lien_holder_admin_fee == None:
                lien_holder.lien_holder_admin_fee = 0;
                governmentTotal += lien_holder.lien_holder_admin_fee;
                adminGrandTotal += lien_holder.lien_holder_admin_fee;
            else:
                governmentTotal += lien_holder.lien_holder_admin_fee;
                adminGrandTotal += lien_holder.lien_holder_admin_fee;

            if lien_holder.lien_holder_litigation_costs == None:
                lien_holder.lien_holder_litigation_costs = 0;
                governmentTotal += lien_holder.lien_holder_litigation_costs;

                litCostGrandTotal += lien_holder.lien_holder_litigation_costs;
            else:
                governmentTotal += lien_holder.lien_holder_litigation_costs;
                litCostGrandTotal += lien_holder.lien_holder_litigation_costs;

            if lien_holder.lien_holder_litigation_expenses == None:
                lien_holder.lien_holder_litigation_expenses = 0;
                governmentTotal += lien_holder.lien_holder_litigation_expenses;
                litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;
            else:
                governmentTotal += lien_holder.lien_holder_litigation_expenses;
                litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;

            if lien_holder.lien_holder_prelitigation_expenses == None:
                lien_holder.lien_holder_prelitigation_expenses = 0;
                governmentTotal += lien_holder.lien_holder_prelitigation_expenses;

                preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;
            else:
                governmentTotal += lien_holder.lien_holder_prelitigation_expenses;
                preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;

            if lien_holder.lien_holder_amount_requested == None:
                lien_holder.lien_holder_amount_requested = 0;
                governmentTotal += lien_holder.lien_holder_amount_requested;

                amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested
            else:
                governmentTotal += lien_holder.lien_holder_amount_requested;
                amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested;


            governmentTotals[int(lien_holder.id)] = governmentTotal;
            grandTotal += governmentTotal


        if lien_holder.category == "bank":
            if lien_holder.lien_holder_face_amount == None:
                lien_holder.lien_holder_face_amount = 0;
                bankTotal += lien_holder.lien_holder_face_amount;

                lienGrandTotal += lien_holder.lien_holder_face_amount; 
            else:
                bankTotal += lien_holder.lien_holder_face_amount;
                lienGrandTotal += lien_holder.lien_holder_face_amount

            if lien_holder.lien_holder_interest_amount == None:
                lien_holder.lien_holder_interest_amount = 0;
                bankTotal += lien_holder.lien_holder_interest_amount;

                interestGrandTotal += lien_holder.lien_holder_interest_amount;
            else:
                bankTotal += lien_holder.lien_holder_interest_amount;
                interestGrandTotal += lien_holder.lien_holder_interest_amount;

            if lien_holder.lien_holder_admin_fee == None:
                lien_holder.lien_holder_admin_fee = 0;
                bankTotal += lien_holder.lien_holder_admin_fee;
                adminGrandTotal += lien_holder.lien_holder_admin_fee;
            else:
                bankTotal += lien_holder.lien_holder_admin_fee;
                adminGrandTotal += lien_holder.lien_holder_admin_fee;

            if lien_holder.lien_holder_litigation_costs == None:
                lien_holder.lien_holder_litigation_costs = 0;
                bankTotal += lien_holder.lien_holder_litigation_costs;
                litCostGrandTotal += lien_holder.lien_holder_litigation_costs;
            else:
                bankTotal += lien_holder.lien_holder_litigation_costs;
                litCostGrandTotal += lien_holder.lien_holder_litigation_costs;

            if lien_holder.lien_holder_litigation_expenses == None:
                lien_holder.lien_holder_litigation_expenses = 0;
                bankTotal += lien_holder.lien_holder_litigation_expenses;
                litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;
            else:
                bankTotal += lien_holder.lien_holder_litigation_expenses;
                litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;

            if lien_holder.lien_holder_prelitigation_expenses == None:
                lien_holder.lien_holder_prelitigation_expenses = 0;
                bankTotal += lien_holder.lien_holder_prelitigation_expenses;
                preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;
            else:
                bankTotal += lien_holder.lien_holder_prelitigation_expenses;
                preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;


            if lien_holder.lien_holder_amount_requested == None:
                lien_holder.lien_holder_amount_requested = 0;
                bankTotal += lien_holder.lien_holder_amount_requested;

                amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested
            else:
                bankTotal += lien_holder.lien_holder_amount_requested;
                amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested;

            bankTotals[int(lien_holder.id)] = bankTotal;
            grandTotal += bankTotal;


        if lien_holder.category == "other":
            if lien_holder.lien_holder_face_amount == None:
                lien_holder.lien_holder_face_amount = 0;
                otherTotal += lien_holder.lien_holder_face_amount;
                lienGrandTotal += lien_holder.lien_holder_face_amount
            else:
                otherTotal += lien_holder.lien_holder_face_amount;
                lienGrandTotal += lien_holder.lien_holder_face_amount

            if lien_holder.lien_holder_interest_amount == None:
                lien_holder.lien_holder_interest_amount = 0;
                otherTotal += lien_holder.lien_holder_interest_amount;
                interestGrandTotal += lien_holder.lien_holder_interest_amount;
            else:
                bankTotal += lien_holder.lien_holder_interest_amount;
                interestGrandTotal += lien_holder.lien_holder_interest_amount;

            if lien_holder.lien_holder_admin_fee == None:
                lien_holder.lien_holder_admin_fee = 0;
                otherTotal += lien_holder.lien_holder_admin_fee;
                adminGrandTotal += lien_holder.lien_holder_admin_fee;
            else:
                otherTotal += lien_holder.lien_holder_admin_fee;
                adminGrandTotal += lien_holder.lien_holder_admin_fee;

            if lien_holder.lien_holder_litigation_costs == None:
                lien_holder.lien_holder_litigation_costs = 0;
                otherTotal += lien_holder.lien_holder_litigation_costs;

                litCostGrandTotal += lien_holder.lien_holder_litigation_costs;
            else:
                otherTotal += lien_holder.lien_holder_litigation_costs;
                litCostGrandTotal += lien_holder.lien_holder_litigation_costs;

            if lien_holder.lien_holder_litigation_expenses == None:
                lien_holder.lien_holder_litigation_expenses = 0;
                otherTotal += lien_holder.lien_holder_litigation_expenses;
                litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;
            else:
                otherTotal += lien_holder.lien_holder_litigation_expenses;
                litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;

            if lien_holder.lien_holder_prelitigation_expenses == None:
                lien_holder.lien_holder_prelitigation_expenses = 0;
                otherTotal += lien_holder.lien_holder_prelitigation_expenses;
                preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;
            else:
                otherTotal += lien_holder.lien_holder_prelitigation_expenses;
                preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;

            if lien_holder.lien_holder_amount_requested == None:
                lien_holder.lien_holder_amount_requested = 0;
                otherTotal += lien_holder.lien_holder_amount_requested;

                amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested
            else:
                otherTotal += lien_holder.lien_holder_amount_requested;
                amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested;

            otherTotals[int(lien_holder.id)] = otherTotal;
            grandTotal += otherTotal;



    for l in other_liens:
        if l.lienholder_set.all():
            for lien_holder in l.lienholder_set.all():
                governmentTotal = 0;
                bankTotal = 0;
            if lien_holder.category == "3rd party":
                if lien.attorney_expenses == None:
                    lien.attorney_expenses = 0
                thirdPartyTotal = lien.lien_amount + lien.total_interest + lien.admin_fee + lien.litigation_costs + lien.litigation_expenses + lien.attorney_expenses;
                setattr(lien, 'rowTotal', thirdPartyTotal)
                grandTotal += thirdPartyTotal;
                lienGrandTotal += lien.lien_amount;
                interestGrandTotal += lien.total_interest;
                adminGrandTotal += lien.admin_fee;
                litCostGrandTotal += lien.litigation_costs;
                preLitGrandTotal += lien.attorney_expenses;
                litExpenseGrandTotal += lien.litigation_expenses;




            

            if lien_holder.category == "government":
                if lien_holder.lien_holder_face_amount == None:
                    lien_holder.lien_holder_face_amount = 0;
                    governmentTotal += lien_holder.lien_holder_face_amount;

                    lienGrandTotal += lien_holder.lien_holder_face_amount;
                else:
                    governmentTotal += lien_holder.lien_holder_face_amount;
                    lienGrandTotal += lien_holder.lien_holder_face_amount;

                if lien_holder.lien_holder_interest_amount == None:
                    lien_holder.lien_holder_interest_amount = 0;
                    governmentTotal += lien_holder.lien_holder_interest_amount;

                    interestGrandTotal += lien_holder.lien_holder_interest_amount;
                else:
                    governmentTotal += lien_holder.lien_holder_interest_amount;
                    interestGrandTotal += lien_holder.lien_holder_interest_amount;

                if lien_holder.lien_holder_admin_fee == None:
                    lien_holder.lien_holder_admin_fee = 0;
                    governmentTotal += lien_holder.lien_holder_admin_fee;
                    adminGrandTotal += lien_holder.lien_holder_admin_fee;
                else:
                    governmentTotal += lien_holder.lien_holder_admin_fee;
                    adminGrandTotal += lien_holder.lien_holder_admin_fee;

                if lien_holder.lien_holder_litigation_costs == None:
                    lien_holder.lien_holder_litigation_costs = 0;
                    governmentTotal += lien_holder.lien_holder_litigation_costs;

                    litCostGrandTotal += lien_holder.lien_holder_litigation_costs;
                else:
                    governmentTotal += lien_holder.lien_holder_litigation_costs;
                    litCostGrandTotal += lien_holder.lien_holder_litigation_costs;

                if lien_holder.lien_holder_litigation_expenses == None:
                    lien_holder.lien_holder_litigation_expenses = 0;
                    governmentTotal += lien_holder.lien_holder_litigation_expenses;
                    litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;
                else:
                    governmentTotal += lien_holder.lien_holder_litigation_expenses;
                    litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;

                if lien_holder.lien_holder_prelitigation_expenses == None:
                    lien_holder.lien_holder_prelitigation_expenses = 0;
                    governmentTotal += lien_holder.lien_holder_prelitigation_expenses;

                    preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;
                else:
                    governmentTotal += lien_holder.lien_holder_prelitigation_expenses;
                    preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;

                if lien_holder.lien_holder_amount_requested == None:
                    lien_holder.lien_holder_amount_requested = 0;
                    governmentTotal += lien_holder.lien_holder_amount_requested;

                    amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested
                else:
                    governmentTotal += lien_holder.lien_holder_amount_requested;
                    amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested;


                governmentTotals[int(lien_holder.id)] = governmentTotal;
                grandTotal += governmentTotal


            if lien_holder.category == "bank":
                if lien_holder.lien_holder_face_amount == None:
                    lien_holder.lien_holder_face_amount = 0;
                    bankTotal += lien_holder.lien_holder_face_amount;

                    lienGrandTotal += lien_holder.lien_holder_face_amount; 
                else:
                    bankTotal += lien_holder.lien_holder_face_amount;
                    lienGrandTotal += lien_holder.lien_holder_face_amount

                if lien_holder.lien_holder_interest_amount == None:
                    lien_holder.lien_holder_interest_amount = 0;
                    bankTotal += lien_holder.lien_holder_interest_amount;

                    interestGrandTotal += lien_holder.lien_holder_interest_amount;
                else:
                    bankTotal += lien_holder.lien_holder_interest_amount;
                    interestGrandTotal += lien_holder.lien_holder_interest_amount;

                if lien_holder.lien_holder_admin_fee == None:
                    lien_holder.lien_holder_admin_fee = 0;
                    bankTotal += lien_holder.lien_holder_admin_fee;
                    adminGrandTotal += lien_holder.lien_holder_admin_fee;
                else:
                    bankTotal += lien_holder.lien_holder_admin_fee;
                    adminGrandTotal += lien_holder.lien_holder_admin_fee;

                if lien_holder.lien_holder_litigation_costs == None:
                    lien_holder.lien_holder_litigation_costs = 0;
                    bankTotal += lien_holder.lien_holder_litigation_costs;
                    litCostGrandTotal += lien_holder.lien_holder_litigation_costs;
                else:
                    bankTotal += lien_holder.lien_holder_litigation_costs;
                    litCostGrandTotal += lien_holder.lien_holder_litigation_costs;

                if lien_holder.lien_holder_litigation_expenses == None:
                    lien_holder.lien_holder_litigation_expenses = 0;
                    bankTotal += lien_holder.lien_holder_litigation_expenses;
                    litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;
                else:
                    bankTotal += lien_holder.lien_holder_litigation_expenses;
                    litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;

                if lien_holder.lien_holder_prelitigation_expenses == None:
                    lien_holder.lien_holder_prelitigation_expenses = 0;
                    bankTotal += lien_holder.lien_holder_prelitigation_expenses;
                    preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;
                else:
                    bankTotal += lien_holder.lien_holder_prelitigation_expenses;
                    preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;


                if lien_holder.lien_holder_amount_requested == None:
                    lien_holder.lien_holder_amount_requested = 0;
                    bankTotal += lien_holder.lien_holder_amount_requested;

                    amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested
                else:
                    bankTotal += lien_holder.lien_holder_amount_requested;
                    amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested;

                bankTotals[int(lien_holder.id)] = bankTotal;
                grandTotal += bankTotal;


            if lien_holder.category == "other":
                if lien_holder.lien_holder_face_amount == None:
                    lien_holder.lien_holder_face_amount = 0;
                    otherTotal += lien_holder.lien_holder_face_amount;
                    lienGrandTotal += lien_holder.lien_holder_face_amount
                else:
                    otherTotal += lien_holder.lien_holder_face_amount;
                    lienGrandTotal += lien_holder.lien_holder_face_amount

                if lien_holder.lien_holder_interest_amount == None:
                    lien_holder.lien_holder_interest_amount = 0;
                    otherTotal += lien_holder.lien_holder_interest_amount;
                    interestGrandTotal += lien_holder.lien_holder_interest_amount;
                else:
                    bankTotal += lien_holder.lien_holder_interest_amount;
                    interestGrandTotal += lien_holder.lien_holder_interest_amount;

                if lien_holder.lien_holder_admin_fee == None:
                    lien_holder.lien_holder_admin_fee = 0;
                    otherTotal += lien_holder.lien_holder_admin_fee;
                    adminGrandTotal += lien_holder.lien_holder_admin_fee;
                else:
                    otherTotal += lien_holder.lien_holder_admin_fee;
                    adminGrandTotal += lien_holder.lien_holder_admin_fee;

                if lien_holder.lien_holder_litigation_costs == None:
                    lien_holder.lien_holder_litigation_costs = 0;
                    otherTotal += lien_holder.lien_holder_litigation_costs;

                    litCostGrandTotal += lien_holder.lien_holder_litigation_costs;
                else:
                    otherTotal += lien_holder.lien_holder_litigation_costs;
                    litCostGrandTotal += lien_holder.lien_holder_litigation_costs;

                if lien_holder.lien_holder_litigation_expenses == None:
                    lien_holder.lien_holder_litigation_expenses = 0;
                    otherTotal += lien_holder.lien_holder_litigation_expenses;
                    litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;
                else:
                    otherTotal += lien_holder.lien_holder_litigation_expenses;
                    litExpenseGrandTotal += lien_holder.lien_holder_litigation_expenses;

                if lien_holder.lien_holder_prelitigation_expenses == None:
                    lien_holder.lien_holder_prelitigation_expenses = 0;
                    otherTotal += lien_holder.lien_holder_prelitigation_expenses;
                    preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;
                else:
                    otherTotal += lien_holder.lien_holder_prelitigation_expenses;
                    preLitGrandTotal += lien_holder.lien_holder_prelitigation_expenses;

                if lien_holder.lien_holder_amount_requested == None:
                    lien_holder.lien_holder_amount_requested = 0;
                    otherTotal += lien_holder.lien_holder_amount_requested;

                    amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested
                else:
                    otherTotal += lien_holder.lien_holder_amount_requested;
                    amountRequestedGrandTotal += lien_holder.lien_holder_amount_requested;

                otherTotals[int(lien_holder.id)] = otherTotal;
                grandTotal += otherTotal;



    return{
        'pictures': pictures,
        'notes': notes,
        'data': data_dict,
        'worksheet': img,
        'governmentTotals': governmentTotals,
        'bankTotals': bankTotals,
        'otherTotals': otherTotals,
        'grandTotal': grandTotal,
        'lienGrandTotal': lienGrandTotal,
        'interestGrandTotal': interestGrandTotal,
        'adminGrandTotal' : adminGrandTotal,
        'litCostGrandTotal': litCostGrandTotal,
        'preLitGrandTotal': preLitGrandTotal,
        'litExpenseGrandTotal': litExpenseGrandTotal,
        'amountRequestedGrandTotal': amountRequestedGrandTotal,
        'otherLiens': other_liens,
        'isAssociated': isAssociated,
    }



@user_passes_test(lambda u: u.is_staff)
def view_info(request, id, lienholderId=None):

    lien = get_object_or_404(Lien, pk=id)
    originalLien = lien
    form = InfoAddLienholderForm()

    if(lienholderId):
        lienHolder = LienHolder.objects.get(pk=lienholderId);
        form2 = InfoEditLienholderForm(instance=lienHolder);

    if (lienholderId):
        lienData = {
            'lien': lien,
            'form': form,
            'form2': form2,
            'lienholderId': lienholderId,
            'originalLien': originalLien
            
        };
    else:
        lienData = {
            'lien': lien,
            'form': form,
            'originalLien': originalLien
        };
    


    if request.POST and 'lienholder-search-input' in request.POST:
        initial = {};
        
        # User wants to autocomplete form fields
        search_query = request.POST['lienholder-search-input']
        # Get the matching lienholder, if any
        search_results = LienHolder.objects.filter(name__icontains=search_query)
        lienholder = search_results[0] if search_results else None
        # Populate lienholder features so that it shows up in the view
        if lienholder:
            lienData['lienholder'] = lienholder
            initial["name"] = lienholder.name
            initial["address"] = lienholder.address
            initial["address2"] = lienholder.address2
            initial["city"] = lienholder.city
            initial["state"] = lienholder.state
            initial["phone"] = lienholder.phone
            initial["zip"] = lienholder.zip
        else:
            lienData["none_found"] = True
        lienData["form"] = InfoAddLienholderForm(initial)
        # return render_to_response('lien/add_lienholder.html', lienData)



    data = get_data(id, lien);

    lienData.update(data);


            
    return render_to_response(
        'lien/info.html',
        lienData
        
    )


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


def get_associated_lien_with_earliest_tax_year(lien, id):
    lien = get_object_or_404(Lien, pk=id)
    # Other liens with the same map number
    liens_w_mapno = Lien.objects.filter(
        map_number=lien.map_number,
        county = lien.county
    ).order_by('tax_year')
    # Remove duplicate liens
    other_liens = [
        l for l in liens_w_mapno
        if l != lien
    ]


    if other_liens:
        earliestLien = other_liens[0]
        return earliestLien
    else:
        return other_liens


@user_passes_test(lambda u: u.is_staff)
def view(request, id):
    """
    Lien view

    Args:
        id - ID for Lien being shown

    Template - lien/view.html
        lien - The lien being shown
        form - For submitting notes
        expense_form - For adding an expense
        payoff_form - For setting the payoff date
    """

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
    
    if len(other_liens) > 0:
        isMultiple = True
    else:
        isMultiple = False


    totalNetPayoff = lien.total_net_payoff


    

    username = request.user.username
    users = [ 'dprater', 'Brenna', 'brenna', 'bprater', 'gary', 'wwbtc']

    fileEditPriv = False

    if username in users:
        fileEditPriv = True
    
    other_liens_face_total = 0
    for l in other_liens:
        if int(l.status.id) is not 75:
            other_liens_face_total += l.lien_amount

    other_liens_total_interest = 0
    for l in other_liens:
        if int(l.status.id) is not 75:
            other_liens_total_interest += l.total_interest
    


    # Add DNB flash message
    if lien.dnb == True:
        messages.add_message(request, messages.ERROR, ' - Do Not Buy Additional Priority Bills')

    if lien.do_not_release == True:
        messages.add_message(request, messages.ERROR, ' - Do Not Release This Lien')

    users_w_payment_perms = [
        'dprater', 'bprater', 'mfox', 'Brenna', 'brenna', 'wwbtc'
    ]
    allow_payment_edits = request.user.username in users_w_payment_perms
    form = NoteForm()
    expense_form = ExpenseForm()
    payment_form = PaymentForm()
    payoff_form = PayoffForm()
    action_date_form = ActionDateForm()
    payment_plan_form = PaymentPlanForm()
    attorney_expense_form = AttorneyExpenseForm()
    pre_lit_expense_form = PreLitExpenseForm()
    lienholder_served_response_form = LienHolderServedResponse()

    
    # Status forms
    primary_status = {}
    secondary_status = {}
    third_status = {}

    if lien.status:
        primary_status['status'] = lien.status.id

    if lien.second_status:
        secondary_status['status'] = lien.second_status.id

    if lien.third_status:
        third_status['status'] = lien.third_status.id

        
    status_form = StatusForm(initial={'status' : lien.status.id, 'second_status' : lien.second_status_id, 'third_status' : lien.third_status_id})

    current_phone1 = lien.current_owner_phone1
    current_phone2 = lien.current_owner_phone2

    edit_current_owner_form = EditCurrentOwnerForm(initial={
            'current_owner_phone1': current_phone1,
            'current_owner_phone2': current_phone2
        })

    return render(request,
        'lien/view.html',
        {
            'lien': lien, 'form':form, 'expense_form': expense_form,
            'payment_form': payment_form, 'payoff_form': payoff_form,
            'action_date_form': action_date_form, 'payment_plan_form': payment_plan_form,
            'status_form': status_form,
            'edit_current_owner_form': edit_current_owner_form,
            'attorney_expense_form': attorney_expense_form,
            'pre_lit_expense_form': pre_lit_expense_form,
            'user': request.user, 'other_liens': other_liens,
            'allow_payment_edits': allow_payment_edits,
            'other_liens_face_total': other_liens_face_total,
            'other_liens_total_interest': other_liens_total_interest,
            'users': users,
            'username': username,
            'is_multiple': isMultiple,
            'totalNetPayoff': totalNetPayoff,
            'fileEditPriv': fileEditPriv,
            'lienholder_served_response_form': lienholder_served_response_form
        }
    )

@user_passes_test(lambda u: u.is_staff)
def mark_letter_sent(request, id, letterType, dateToSet=date.today()):
    lien = get_object_or_404(Lien, pk=id) # Gets the lien from the id

    letterToProp = {
        "letter_one": "date_first_letter",
        "letter_two": "date_second_letter",
        "letter_three": "date_third_letter", 
        "letter_four": "date_fourth_letter",
        "first_letter_assignment": "date_first_letter_assignment",
        "foreclosure_warning_letter": "foreclosure_warning_letter",
        "occupant_letter": "date_occupant_letter",
        "out_of_stat": "date_out_of_stat",
        'annual_letter': "date_annual_letter",
    }

    # Check if a date already exists
    hasDate = getattr(lien, letterToProp[letterType])


    # if a date does not exist
    if not hasDate:
        setattr(lien, letterToProp[letterType], dateToSet)
        activity.create_update_log(
            lien = lien,
            user = request.user,
            object_id = -1,
            object_revision_id = -1,
            object_type = str(letterToProp[letterType])
        )
        lien.save()
    # if one does exist, we will just remove it
    else:
        setattr(lien, letterToProp[letterType], None)
        lien.save()
        activity.create_update_log(
            lien = lien,
            user = request.user,
            object_id = -1,
            object_revision_id = -1,
            object_type = str(letterToProp[letterType])
        )

    return HttpResponseRedirect(reverse('lien-view', args = [id,]))



@user_passes_test(lambda u: u.is_staff)
def change_status(request, id):

    # Gets the lien from the id
    lien = get_object_or_404(Lien, pk=id)

    


    handleMultiple = request.POST.get('add-status-associated', None) 
    date, time = (request.POST.get('mc_sale_date'), request.POST.get('mc_sale_time'))
    
    if request.method == 'POST':
        form = StatusForm(request.POST)
        
        if form.is_valid():

            # We will get this first, so we know what we changing from
            previousFirstStatusID = lien.status_id if lien.status_id is not None else -1
            previousSecondStatusID = lien.second_status_id if lien.second_status_id is not None else -1
            previousThirdStatusID = lien.third_status_id if lien.third_status_id is not None else -1


            # This one is used for something completely different
            oldThirdStatusID = lien.third_status_id
            if oldThirdStatusID is None:
                oldThirdStatusID = 0

            primary = form.cleaned_data['status']
            second = form.cleaned_data['second_status']
            third = form.cleaned_data['third_status']

            # There is no reason to check if none here, since we are submitting all at once. We also need the 'Nones'
            lien.status = primary
            lien.second_status = second
            lien.third_status = third






 
            # Create an activity entry log ---------------------------------------------
            # Okay we need to check if none here- I lied in the above comments. But for good reason.
            if primary is None:   
                first_id = -1
            if second is None:
                second_id = -1
            if third is None:
                third_id = -1

            
            if previousFirstStatusID != (primary.id if primary is not None else first_id):
                # First Status
                activity.create_update_log(
                    lien = lien,
                    user = request.user,
                    object_id = int(previousFirstStatusID),
                    object_revision_id = int(primary.id) if primary is not None else first_id,
                    object_type = "Primary Status"

                )


            if previousSecondStatusID != (second.id if second is not None else second_id):
                # Second Status
                activity.create_update_log(
                    lien = lien,
                    user = request.user,
                    object_id = int(previousSecondStatusID),
                    object_revision_id = int(second.id) if second is not None else second_id,
                    object_type = "Second Status"

                )

            if previousThirdStatusID != (third.id if third is not None else third_id):
                # Third Status
                activity.create_update_log(
                    lien = lien,
                    user = request.user,
                    object_id = int(previousThirdStatusID),
                    object_revision_id = int(third.id) if third is not None else third_id,
                    object_type = "Third Status"

                )
            
                # End Activity Entry Log ----------------------------------------

            # Title Ordered ID is 35
            if int(oldThirdStatusID) == 35:
                if lien.order_title:
                    titleOrdered = False;
                    setattr(lien, 'order_title', titleOrdered)

            if date and time:

                # convert to python datetime object
                def convert_datetime(mc_sale_scheduled):
                    '''
                    check valid formats of new dates entered and pre-existing
                    mc sale dates. New mc sale scheduled initial time 
                    value of input type=time sends in format %H:%M.
                    '''
                    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
                        try:
                            return datetime.strptime(mc_sale_scheduled, fmt)
                        except ValueError:
                            pass
                    raise ValueError('no valid date/time format')
                
                date_time = ' '.join([date,time])
                mc_sale_scheduled = convert_datetime(date_time)
                
                mc_date = mc_sale_scheduled.date()
                mc_time = mc_sale_scheduled.time()
                # update lien mc_sale_scheduled
                lien.mc_sale_date = mc_date
                lien.mc_sale_time = mc_time
            
            lien.save()

            if handleMultiple == 'yes':
                otherLiens = get_other_liens(lien, lien.id)
                
                for l in otherLiens:
                    # Update mc sale scheduled time
                    if date and time:
                        l.mc_sale_date = mc_date
                        l.mc_sale_time = mc_time

                    oldThirdStatusID = l.third_status_id
                    if oldThirdStatusID is None:
                        oldThirdStatusID = 0

                    # Title Ordered ID is 35
                    if int(oldThirdStatusID) == 35:
                        if l.order_title:
                            titleOrdered = False;
                            setattr(l, 'order_title', titleOrdered)


                    # We will get this first, so we know what we changing from
                    previousFirstStatusID = l.status_id if l.status_id is not None else -1
                    previousSecondStatusID = l.second_status_id if l.second_status_id is not None else -1
                    previousThirdStatusID = l.third_status_id if l.third_status_id is not None else -1

                    l.status = primary
                    l.second_status = second
                    l.third_status = third


                    l.save()


                    # Create an activity entry log ---------------------------------------------
                    # Okay we need to check if none here- I lied in the above comments. But for good reason.
                    if primary is None:   
                        first_id = -1
                    if second is None:
                        second_id = -1
                    if third is None:
                        third_id = -1

                    
                    if previousFirstStatusID != (primary.id if primary is not None else first_id):
                        # First Status
                        activity.create_update_log(
                            lien = l,
                            user = request.user,
                            object_id = int(previousFirstStatusID),
                            object_revision_id = int(primary.id) if primary is not None else first_id,
                            object_type = "Primary Status"

                        )


                    if previousSecondStatusID != (second.id if second is not None else second_id):
                        # Second Status
                        activity.create_update_log(
                            lien = l,
                            user = request.user,
                            object_id = int(previousSecondStatusID),
                            object_revision_id = int(second.id) if second is not None else second_id,
                            object_type = "Second Status"

                        )

                    if previousThirdStatusID != (third.id if third is not None else third_id):
                        # Third Status
                        activity.create_update_log(
                            lien = l,
                            user = request.user,
                            object_id = int(previousThirdStatusID),
                            object_revision_id = int(third.id) if third is not None else third_id,
                            object_type = "Third Status"

                        )
                    
                        # End Activity Entry Log ----------------------------------------


                    

        
        return HttpResponseRedirect(reverse('lien-view', args = [id,]))


    return HttpResponseRedirect(reverse('lien-index'))

def delete_lienholder(request, lienholder_id, lien_id):
    
    # If the ids exist
    if lienholder_id and lien_id:
        lienholder = LienHolder.objects.filter(lien_id = lien_id, id = lienholder_id)
        lien = get_object_or_404(Lien, pk=int(lien_id))
        
        # Check if lienholder exists
        if lienholder:
            for lh in lienholder:

                # We need to add a tracker here
                activity.create_delete_log(
                    user = request.user,
                    lien = lien,
                    object_id = int(lh.id),
                    object_type = "Lienholder"
                )

                lh.delete()

            # Success message
            messages.add_message(request, messages.SUCCESS, 'Deleted Lienholder Successfully.')

        
    return HttpResponseRedirect(reverse('lien-view', args = [lien_id,]))



@user_passes_test(lambda u: u.is_staff)
def add_note(request, id):
    """
    Add note to a lien

    If successful, redirects back to lien view
    """
    if request.method == 'POST':
        form = NoteForm(request.POST)
        if form.is_valid():
            try:
                lien = Lien.objects.get(pk=id)
            except Lien.DoesNotExist:
                return HttpResponseRedirect(reverse('lien-index'))
            if form.cleaned_data['action_date']:

                # Handle the original lien first
                lien.action_date = form.cleaned_data['action_date']
                lien.save()

                # If we want to add to the associated liens
                handleMultipleAc = request.POST.get('add-ac-associated', None)
                if handleMultipleAc and handleMultipleAc == 'yes':
                    otherLiens = get_other_liens(lien, lien.id)
                    for l in otherLiens:
                        l.action_date = form.cleaned_data['action_date'];
                        l.save();

            # --------------------------------------- Starting note section ---------------------------------------

            # We can save this one no matter what
            note = Note.objects.create(body=form.cleaned_data['note'], user=request.user, lien=lien)

            # We need to add a tracker here
            activity.create_add_log(
                user = request.user,
                lien = lien,
                object_id = note.id,
                object_type = "Note"
            )


            # If user wants to add note to associated liens
            handleMultiple = request.POST.get('add-note-associated', None)
            if handleMultiple and handleMultiple == 'yes':
                otherLiens = get_other_liens(lien, lien.id)
                for l in otherLiens:
                    note = Note.objects.create(body=form.cleaned_data['note'], user=request.user, lien=l)

                    # We need to add a tracker here
                    activity.create_add_log(
                        user = request.user,
                        lien = l,
                        object_id = note.id,
                        object_type = "Note"
                    )


        return HttpResponseRedirect(reverse('lien-view', args = [id,]))
    return HttpResponseRedirect(reverse('lien-index'))

@user_passes_test(lambda u: u.is_staff)
def add_expense(request, id):
    """
    Add expense to lien

    If the form is not valid, displays the form for correction

    Args:
        id - ID of lien

    Template - lien/expense_add.html (only used if form isn't valid)
        expense_form - Form for adding expense
        lien - Lien the expense is being added to
    """
    if request.method == 'POST':
        try:
            lien = Lien.objects.get(pk=id)
        except Lien.DoesNotExist:
            return HttpResponseRedirect(reverse('lien-index'))
        

        
        # Since we are passing the expense class ID as a default/initial value. The form.cleaned_data will not grab it.
        # Instead, we need to hack the request.POST to get that ID number. 
        POST = request.POST.copy();
        expenseID = POST['expense_class'];

        if expenseID == 15:
            form = AttorneyExpenseForm(request.POST)
        elif expenseID == 16:
            form = PreLitExpenseForm(request.POST)
        else:
            form = ExpenseForm(request.POST)

       
        

        if form.is_valid():
            expense = Expense.objects.create(note=form.cleaned_data['note'],
                    amount=form.cleaned_data['amount'],
                    lien=lien,
                    expense_class_id=expenseID,
                    attorney=form.cleaned_data['attorney'],
                    effective_date=form.cleaned_data['expense_date'],
                    user=request.user
                    )

            activity.create_add_log(
                user = request.user,
                lien = lien,
                object_id = expense.id,
                object_type = "Expense"
            )
            return HttpResponseRedirect(reverse('lien-view', args = [id,]))
        else:
            # If the expense ID is 15, this is the Foreclosure Attorney Billing. We need the other form and template file rendered
            if expenseID == 15:
                form = AttorneyExpenseForm(request.POST)
                return render_to_response('lien/expense_attorney_add.html', {'attorney_expense_form': form, 'lien': lien})
            elif expenseID == 16:
                form = PreLitExpenseForm(request.POST)
                return render_to_response('lien/expense_pre_lit_add.html', {'pre_lit_expense_form': form, 'lien': lien})
            else:
                return render_to_response('lien/expense_add.html', {'expense_form': form, 'lien': lien})
    return HttpResponseRedirect(reverse('lien-index'))



@user_passes_test(lambda u: u.is_staff)
def add_pre_lit_expense(request, id):
    """
    Add expense to lien

    If the form is not valid, displays the form for correction

    Args:
        id - ID of lien

    Template - lien/expense_add.html (only used if form isn't valid)
        expense_form - Form for adding expense
        lien - Lien the expense is being added to
    """
    if request.method == 'POST':
        try:
            lien = Lien.objects.get(pk=id)
        except Lien.DoesNotExist:
            return HttpResponseRedirect(reverse('lien-index'))
        

        
        # Since we are passing the expense class ID as a default/initial value. The form.cleaned_data will not grab it.
        # Instead, we need to hack the request.POST to get that ID number. 
        POST = request.POST.copy();
        expenseID = POST['expense_class'];

        form = PreLitExpenseForm(request.POST)

        

       
        

        if form.is_valid():
            expense = Expense.objects.create(note=form.cleaned_data['note'],
                    amount=form.cleaned_data['amount'],
                    lien=lien,
                    expense_class_id=expenseID,
                    effective_date=form.cleaned_data['expense_date'],
                    user=request.user
                    )
            return HttpResponseRedirect(reverse('lien-view', args = [id,]))
        else:
            return render_to_response('lien/expense_attorney_add.html', {'pre_lit_expense_form': form, 'lien': lien})
    return HttpResponseRedirect(reverse('lien-index'))



@user_passes_test(lambda u: u.is_staff)
def add_attorney_expense(request, id):
    """
    Add expense to lien

    If the form is not valid, displays the form for correction

    Args:
        id - ID of lien

    Template - lien/expense_add.html (only used if form isn't valid)
        expense_form - Form for adding expense
        lien - Lien the expense is being added to
    """
    if request.method == 'POST':
        try:
            lien = Lien.objects.get(pk=id)
        except Lien.DoesNotExist:
            return HttpResponseRedirect(reverse('lien-index'))
        

        
        # Since we are passing the expense class ID as a default/initial value. The form.cleaned_data will not grab it.
        # Instead, we need to hack the request.POST to get that ID number. 
        POST = request.POST.copy();
        expenseID = POST['expense_class'];

        form = AttorneyExpenseForm(request.POST)

       
        

        if form.is_valid():
            expense = Expense.objects.create(note=form.cleaned_data['note'],
                    amount=form.cleaned_data['amount'],
                    lien=lien,
                    expense_class_id=expenseID,
                    attorney=form.cleaned_data['attorney'],
                    effective_date=form.cleaned_data['expense_date'],
                    user=request.user
                    )
            return HttpResponseRedirect(reverse('lien-view', args = [id,]))
        else:
            return render_to_response('lien/expense_attorney_add.html', {'attorney_expense_form': form, 'lien': lien})
    return HttpResponseRedirect(reverse('lien-index'))

@user_passes_test(lambda u: u.is_staff)
def add_payment(request, id):
    """
    Add payment to lien

    If the form is not valid, displays the form for correction

    Args:
        id - ID of lien

    Template - lien/payment_add.html (only used if form isn't valid)
        payment_form - Form for adding payment
        lien - Lien the expense is being added to
    """
    if request.method == 'POST':
        try:
            lien = Lien.objects.get(pk=id)
        except Lien.DoesNotExist:
            return HttpResponseRedirect(reverse('lien-index'))
        form = PaymentForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['payment_plan_fee']:

                # Get current month and year
                today = datetime.today();
                month = today.month;
                year = today.year;

                days = monthrange(year, month)
                firstDay, numOfDays = days

                firstDay = datetime(year, month, 1);
                lastDay = datetime(year, month, numOfDays);

                # Check if payment plan fee already exists this month
                payments = Payment.objects.filter(lien_id = id, date__range=(firstDay, lastDay), payment_plan_fee = 8.00);

                # If there are no payments, add the payment plan fee
                if len(payments) == 0:
                    lien.add_payment_plan_fee()
            payment = Payment.objects.create(payor=form.cleaned_data['payor'],
                                             amount=form.cleaned_data['amount'],
                                             type=form.cleaned_data['type'],
                                             instrument_number=form.cleaned_data['instrument_number'],
                                             lien=lien,
                                             entered_by=request.user)

            activity.create_add_log(
                user = request.user,
                lien = lien,
                object_id = payment.id,
                object_type = "Payment"
            )
            return HttpResponseRedirect(reverse('lien-view', args = [id,]))
        else:
            return render_to_response('lien/payment_add.html', {'payment_form': form, 'lien': lien})
    return HttpResponseRedirect(reverse('lien-index'))

@user_passes_test(lambda u: u.is_staff)
def edit_expense(request, id):
    
    def getContext(expense):

        expense_dict = expense.__dict__
        lien = get_object_or_404(Lien, pk=expense.lien_id)
        expense_class = expense.expense_class_id

        if request.POST:
            if expense_class == 15:
                form = AttorneyExpenseForm(request.POST)
            elif expense_class == 16:
                form = PreLitExpenseForm(request.POST)
            else:
                form = ExpenseForm(request.POST)
        else:
            # the expense_date needs formatting when pulled from the database (MM/DD/YYYY).
            expense_dict['expense_date'] = expense_dict['expense_date'].strftime('%m/%d/%Y')

            if expense_class == 15:
                form = AttorneyExpenseForm(initial=expense_dict)
            elif expense_class == 16:
                form = PreLitExpenseForm(initial=expense_dict)
            else:
                form = ExpenseForm(initial=expense_dict)

            # attorney has been stored as varchar in the database there is inconsistency for the attorney name. 
            # for some expenses the attorney field is not set, in this case let the user update manually.
            if expense_dict['attorney']:
                try:
                    expense_attorney = expense_dict['attorney']
                    expense_dict['attorney'] = Attorney.objects.get(name=expense_attorney).id
                except:
                    msg = 'The query parameter for attorney: "' + expense_attorney + '" was not found, update the Foreclosure Attorney field to edit this expense.'
                    messages.warning(request, msg)
            
        context = {
            'expense_class': expense_class,
            'lien': lien,
            'expense_form': form,
            'expense_id': expense.id
            }

        return (context, form)

    # update the expense object data
    if request.POST:
        expense = get_object_or_404(Expense, pk=id)
        context, form = getContext(expense)

        if form.is_valid():
            
            for k,v in form.cleaned_data.iteritems():
                if k == 'attorney':
                    v = v.name
                setattr(expense, k, v)

            expense.save()

            lien = get_object_or_404(Lien, pk=expense.lien_id)

            activity.create_update_log(
                lien = lien,
                user = request.user,
                object_id = int(expense.id),
                object_revision_id = int(expense.id),
                object_type = "Expense"
            )

            return HttpResponseRedirect(reverse('lien-view', args = [expense.lien_id,]))
        return render_to_response('lien/expense_edit.html', context)

    # prepopulate the form with current expense object data
    expense = get_object_or_404(Expense, pk=id)
    context, form = getContext(expense)
    
    return render(request,'lien/expense_edit.html',context)

@user_passes_test(lambda u: u.is_staff)
def calc_payoff(request, id):
    """
    Calculates the payoff based on date given through form
    Sets the potential payoff date to the date entered

    Args:
        id - ID of lien

    If form fails:
        Template - lien/payoff_calc.html
            payoff_form - Form for payoff
            lien - Lien for calcuations

    If form success:
        Template - lien/payoff_calc.html
            payoff_form - Form for payoff
            lien - Lien for calcuations
            calc_date - Date entered in form
    """
    if request.method == 'POST':
        try:
            lien = Lien.objects.get(pk=id)
        except Lien.DoesNotExist:
            return HttpResponseRedirect(reverse('lien-index'))
        form = PayoffForm(request.POST)
        if form.is_valid():
            lien.potential_payoff_date = form.cleaned_data['payoff_date']
            lien.save()
            lien.set_calc_date(form.cleaned_data['payoff_date'])

            other_liens = get_other_liens(lien, lien.id)
            if other_liens:
                for l in other_liens:
                    l.potential_payoff_date = form.cleaned_data['payoff_date']
                    l.save()
                    l.set_calc_date(form.cleaned_data['payoff_date'])
            return redirect('lien-view', lien.id)                                        
        else:
            return redirect('lien-view', lien.id)
    return HttpResponseRedirect(reverse('lien-index'))

@user_passes_test(lambda u: u.is_staff)
def calc_payment_plan(request, id):
    try:
        lien = Lien.objects.get(pk=id)
    except Lien.DoesNotExist:
        return HttpResponseRedirect(reverse('lien-index'))
    form = PaymentPlanForm(request.GET)

    if form.is_valid():
        d1 = form.cleaned_data['start_date']
        d2 = form.cleaned_data['end_date']
        day_of_month = form.cleaned_data['day_of_month']

        # What does the +1 do here?
        months = (d2.year - d1.year)*12 + d2.month - d1.month + 1

        # Can't have a zero month
        if months == 0:
            months = 1

        # The number of months the plan will exist, muliplied by $8 per month
        fees = Decimal('8.00') * Decimal(str(months))

        lien.attorney_expenses = lien.get_attorney_fee
        lien.set_calc_date(form.cleaned_data['end_date'])

        # have to subtract out fees here b/c it is added to the payoff_letter_toal and again here by using the months
        # using the months to calculate here is correct.
        # The payoff is 1 month short of interest payments when compared to the payoff table and payment plan table
        # Short term, adding the month interest here
        # TO DO: reconcile why total_payoff_interest is one month less here
        payoff = lien.payoff_letter_revised_total_owed + fees - lien.get_payment_breakdown_total('payment_plan_fee')

        last_payment = Decimal('0.00')

        if not form.cleaned_data['monthly_amount']:
            monthly_amount = payoff / Decimal(str(months))
            last_payment = monthly_amount
        else:
            monthly_amount = Decimal(str(form.cleaned_data['monthly_amount']))
            if monthly_amount > payoff:
                last_payment = payoff - monthly_amount
            elif months * monthly_amount > payoff:
                last_payment = payoff % monthly_amount
            elif months * monthly_amount < payoff:
                last_payment = payoff - ((months - Decimal('1')) * monthly_amount)

        #round monthly amount to elimiate errors in accepting long floating point numbers
        monthly_amount = round(monthly_amount, 4)

        payment_plan = {
            'start_date': d1.strftime("%m/%d/%Y"),
            'end_date': d2.strftime("%m/%d/%Y"),
            'monthly_amount': monthly_amount,
            'payoff': payoff,
            'months': months,
            'day_of_month': day_of_month,
            'last_payment': last_payment,
        }

        query = urllib.urlencode(payment_plan)

        context = {
            'months': months,
            'fees': fees,
            'lien': lien,
            'last_payment': last_payment,
            'payment_plan_form': form,
            'query': query
        }

        # Add in the payment plan values
        context.update(payment_plan)

        return render_to_response('lien/payment_plan_calc.html', context)
    else:
        print('SORRY NOT VALID')

def accept_payment_plan(request, id):
    try:
        lien = Lien.objects.get(pk=id)
    except Lien.DoesNotExist:
        return HttpResponseRedirect(reverse('lien-index'))
    form = PaymentPlanAcceptForm(request.GET)

    last_payment = request.GET.get('last_payment')
    payoff_total = request.GET.get('payoff')

    if form.is_valid():
        lien.attorney_expenses = lien.get_attorney_fee
        lien.potential_payoff_date = form.cleaned_data['end_date']
        lien.date_begin_payment_plan = form.cleaned_data['start_date']
        lien.payment_plan_amount = form.cleaned_data['monthly_amount']
        lien.payment_day_of_month = form.cleaned_data['day_of_month']
        lien.payment_plan_last_payment = last_payment
        lien.payment_plan_total_payoff = payoff_total
        lien.save()
    else:
        print form.errors

    return HttpResponseRedirect(reverse('lien-view', args = [id,]))

@user_passes_test(lambda u: u.is_staff)
def set_action_date(request, id):
    if request.method == 'POST':
        try:
            lien = Lien.objects.get(pk=id)
        except Lien.DoesNotExist:
            return HttpResponseRedirect(reverse('lien-index'))
        form = ActionDateForm(request.POST)
        if form.is_valid():
            lien.action_date = form.cleaned_data['set_action_date']
            messages.add_message(request, messages.SUCCESS, 'Action Date Successfully Changed.')
            lien.save()
        return HttpResponseRedirect(reverse('lien-view', args = [id,]))

@user_passes_test(lambda u: u.is_staff)
def index(request):
    '''
    Tracker index page with pie chart display.
    '''
    search_form = SearchForm()
    filter_form = FilterStatusForm()
    date_form = DateSearchForm()
    county_form = CountyDateSearchForm()
    upload_form = UploadForm()
    payment_form = PaymentReportForm()
    unpaid_form = UnpaidBillsForm()
    sale_form = SaleInspectionForm();

    if request.GET.__contains__('skip-cache') and request.GET['skip-cache'] == 'true':
        raw_result = get_report_info(
            'status_report',
            skip_cache=True
        )
    else:
        raw_result = get_report_info('status_report')

    fc_result_dict = raw_result['result']
    unix_date_run = raw_result['date_run']
    data_date_run = real_time.strftime(
        '%m/%d/%Y %I:%M %p',
        real_time.localtime(unix_date_run)
    )

    status_data = set_in(fc_result_dict, ['data_date_run'], data_date_run)
    
    # get the cached composite data with status report
    context = status_data

    # get filtered data and return updated context
    if request.method == 'POST':
        if filter_form.is_valid:
            filter_form = FilterStatusForm(request.POST)
            search_form = SearchForm()

            context['search_form'] = search_form
            context['filter_form'] = filter_form

            # send me to status filter module.
            try:
                post_dict = request.POST.dict()
                context = sf.filter_by_options(post_dict,context)

            except Exception as e:
                res = 'Empty result set, please try another search.'
                messages.error(request, res)
                return render(request,'reporting/lien_status_report_filtering.html', context)
        else:
            return render_to_response('reporting/lien_status_report_filtering.html', context)
        
    context['search_form'] = search_form
    context['filter_form'] = filter_form
    context['date_form'] = date_form
    
    admins = getAdminUsers()
    context['isAdmin'] = True if request.user.username in admins else False

    reportAdmins = getMSCPTaxPoolUsers();
    context['isReportAdmin'] = True if request.user.username in reportAdmins else False

    return render_to_response('reporting/lien_status_report_filtering.html', context)

@user_passes_test(lambda u: u.is_staff)
def advanced_search(request):

    date_form = DateSearchForm()
    county_form = CountyDateSearchForm()
    upload_form = UploadForm()
    payment_form = PaymentReportForm()
    unpaid_form = UnpaidBillsForm()
    sale_form = SaleInspectionForm()
    expense_form = ExpenseSearchForm();

    return render_to_response('lien/advanced_search.html', {
        'sale_form':sale_form, 'date_form': date_form, 'upload_form': upload_form, 'payment_form': payment_form, 'unpaid_form' : unpaid_form, 'expense_form' : expense_form}
    )




@user_passes_test(lambda u: u.is_staff)
def backup(request):
    """
    Index page for lien data project

    Template - lien/index.html
        form - Search form
        date_form - Date filter form
        upload_form - Used for uploading files for import
    """
    form = SearchForm()
    date_form = DateSearchForm()
    county_form = CountyDateSearchForm()
    upload_form = UploadForm()
    payment_form = PaymentReportForm()
    unpaid_form = UnpaidBillsForm()
    sale_form = SaleInspectionForm();

    users_w_payment_perms = [
        'dprater', 'bprater', 'wwbtc'
    ]

    # Get date for filename
    date = datetime.today().strftime('%Y-%m-%d');
    filename = date +'.csv';

    allow_inspections_view = request.user.username in users_w_payment_perms

    purchased_properties = Lien.objects.filter(property_purchased=True)
    special_assets = Lien.objects.filter(special_asset=True)

    # Set the action date to today
    # date_form.fields['action_date'].initial = datetime.now().strftime('%m/%d/%Y')

    return render_to_response('lien/index.html', {'filename': filename, 'sale_form':sale_form, 'form': form, 'date_form': date_form, 'upload_form': upload_form,
                                                  'payment_form': payment_form, 'unpaid_form' : unpaid_form, 'allow_inspections' : allow_inspections_view })

@user_passes_test(lambda u: u.is_staff)
def export(request):
    """
    Exports all liens

    Returns CSV file
    """
    liens = Lien.objects.all()
    return export_to_csv(liens)

@user_passes_test(lambda u: u.is_staff)
def short_export(request):
    """
    Exports all liens but not as many fields

    Returns CSV file
    """
    liens = Lien.objects.all()
    return export_to_csv(liens, short_export=True)

@user_passes_test(lambda u: u.is_staff)
def export_without_notes(request):
    """
    Exports all liens without the notes

    Returns CSV file
    """
    liens = Lien.objects.all()
    return export_to_csv(liens, with_notes=False)

@user_passes_test(lambda u: u.is_staff)
def export_dnb_liens(request):
    """
    Exports all liens that have the do not buy flag
    Returns csv file
    """
    liens = Lien.objects.filter(dnb=True, date_paid__isnull=True)
    
    dnb_list = [['County', 'Tax Year','Owner', 'Current Owner', 'Map Number', 'Property Location', 'Property City', 'Property State', 'Property Zip', 'Date Paid']]

    for l in liens:
        temp_list = []
        temp_list.append(l.county.name)
        temp_list.append(l.tax_year)
        temp_list.append(l.owner_name)
        temp_list.append(l.current_owner_name)
        temp_list.append(l.map_number)
        temp_list.append(l.property_location)
        temp_list.append(l.property_city)
        temp_list.append(l.property_state)
        temp_list.append(l.property_zip)
        temp_list.append(l.date_paid)
        dnb_list.append(temp_list)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="dnb-export.csv"'

    writer = csv.writer(response)
    for l in dnb_list:
        writer.writerow(l)

    return response

@user_passes_test(lambda u: u.is_staff)
def letter_one_report(request):
    """
    Report for all liens that need the first letter

    This view also sets the `date_first_letter` to today

    Template - lien/letter_one_report.html
        liens - Liens that need the first letter
    """
    liens = Lien.objects.letter_one()
    for lien in liens:
        lien.date_first_letter = date.today()
        lien.save()
    return render_to_response('lien/letter_one_report.html', {'liens': liens})

@user_passes_test(lambda u: u.is_staff)
def letter_two_report(request):
    """
    Report for all liens that need the second letter

    This view also sets the `date_second_letter` to today

    Template - lien/letter_one_report.html
        liens - Liens that need the second letter
    """
    liens = Lien.objects.letter_two()
    for lien in liens:
        lien.date_second_letter = date.today()
        lien.save()
    return render_to_response('lien/letter_two_report.html', {'liens': liens})

@user_passes_test(lambda u: u.is_staff)
def import_liens(request):
    """
    Imports liens from a CSV file

    Takes a CSV from the `UploadForm`

    Template - lien/import_results.html
        liens - Liens imported
        not_imported - Rows not imported
        not_imported_count - Number of liens not imported
        count - Number of liens imported
    """
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            file_loc = '%s/%s.csv' % (settings.UPLOAD_DIR, request.user.username)
            handle_uploaded_file(request.FILES['file'], file_loc)
            liens = ImportLiens(file_loc, request=request)
            os.remove(file_loc)
            return render_to_response(
                'lien/import_results.html', {
                'liens': liens.lien_list,
                'not_imported': liens.lien_dup,
                'not_imported_count': len(liens.lien_dup),
                'count': len(liens.lien_list)}
            )
        

@user_passes_test(lambda u: u.is_staff)
def import_lien_holders(request):
    """
    Imports lien holders from file

    Takes a CSV from the `UploadForm`

    Template - lien/import_lien_holder_results.html
        lien_holders - Lien holders imported
        errors - Any errors that were encountered
        count - Number of liens imported
    """
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            file_loc = '%s/%s.csv' % (settings.UPLOAD_DIR, request.user.username)
            handle_uploaded_file(request.FILES['file'], file_loc)
            liens = ImportLienHolders(file_loc)
            os.remove(file_loc)
            return render_to_response(
                'lien/import_lien_holder_results.html', {
                    'lien_holders': liens.lien_holder_list,
                    'errors': liens.error_list,
                    'count': len(liens.lien_holder_list),
                }
            )


@user_passes_test(lambda u: u.is_staff)
def import_others(request):
    """
    Imports lien holders from file

    Takes a CSV from the `UploadForm`

    Template - lien/import_lien_holder_results.html
        lien_holders - Lien holders imported
        errors - Any errors that were encountered
        count - Number of liens imported
    """
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            file_loc = '%s/%s.csv' % (settings.UPLOAD_DIR, request.user.username)
            handle_uploaded_file(request.FILES['file'], file_loc)
            liens = ImportOthers(file_loc, request)
            os.remove(file_loc)
            return render_to_response(
                'lien/import_results.html', {
                    'lien': liens.lien_list,
                    'errors': liens.error_list,
                    'count': len(liens.lien_list),
                }
            )

@user_passes_test(lambda u: u.is_staff)
def import_changes(request):
    """
    Imports changes on liens from a CSV file

    Takes a CSV from the `UploadForm`

    Template - lien/import_results.html
        liens - Liens changed
        errors - Errors encountered during change
        count - Number of liens changed
        not_changed_count - Number of liens not changed
    """
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            file_loc = '%s/%s_changes.csv' % (settings.UPLOAD_DIR, request.user.username)
            handle_uploaded_file(request.FILES['file'], file_loc)
            liens = ImportLiens(file_loc, changes=True)
            os.remove(file_loc)
            return render_to_response(
                'lien/import_change_results.html', {
                    'liens': liens.lien_list,
                    'errors': liens.error_list,
                    'count': len(liens.lien_list),
                    'not_changed_count': len(liens.error_list),
                }
            )

@user_passes_test(lambda u: u.is_staff)
def import_fields(request):
    """
    Lists fiels available for importing

    Template - lien/import_fields.html
        fields - Available fields
    """
    fields = []
    custom_fields = []
    for field in Lien._meta.fields:
        if field.name != 'id':
            fields.append((field.verbose_name, field.name))

    for field in Investor._meta.fields:
        if field.name != 'id':
            fields.append(("Investor %s" % field.verbose_name, "investor_%s" % field.name))

    for field in Expense._meta.fields:
        if field.name != 'id':
            if field.name == 'expense_class':
                field.name = 'expense_type'
            fields.append((field.verbose_name, field.name))

    
    custom_fields.append(('Fees from bulk purchase', 'fees_from_bulk_purchase'))
    custom_fields.append(('Total Payments', 'total_payments'))
    custom_fields.append(('Payment Note (Payor)', 'payment_note'))

    return render_to_response('lien/import_fields.html', {'fields': fields, 'custom_fields':custom_fields})


@user_passes_test(lambda u: u.is_staff)
def info_add_lienholder(request, id, *leinholderId):
    """
    Add a lienholder to a lien.

    Params:
        id: refers to the id of the lien
        *lienholder: the lienholder id, so that we can auto-fill those fields
    """

    lien = get_object_or_404(Lien, pk=id)
    initial = {
        "lien": lien
    }
    template_map = {
        "id": id,
        "lien": lien,
    }
    if request.POST and 'lienholder-search-input' in request.POST:
        # User wants to autocomplete form fields
        search_query = request.POST['lienholder-search-input']
        # Get the matching lienholder, if any
        search_results = LienHolder.objects.filter(name__icontains=search_query)
        lienholder = search_results[0] if search_results else None
        # Populate lienholder features so that it shows up in the view
        if lienholder:
            template_map['lienholder'] = lienholder
            initial["name"] = lienholder.name
            initial["address"] = lienholder.address
            initial["address2"] = lienholder.address2
            initial["city"] = lienholder.city
            initial["state"] = lienholder.state
            initial["phone"] = lienholder.phone
            initial["zip"] = lienholder.zip
        else:
            template_map["none_found"] = True
        template_map["form"] = InfoAddLienholderForm(initial)
        return render_to_response('lien/info.html', template_map)
    elif request.POST:
        
        # User wants to create new lienholder
        new_lienholder = LienHolder(lien=lien)
        
        form_data =request.POST.dict()
        lienholder_form = InfoAddLienholderForm(
            form_data,
            instance=new_lienholder
        )
        if lienholder_form.is_valid():
            lienholder_form.save()
            return redirect('lien-view_info', id)
        else:
            template_map["form"] = lienholder_form
            return render_to_response('lien/info.html', template_map)

    else:
        template_map["form"] = AddLienholderForm(initial)
        return render_to_response('lien/info.html', template_map)
        

@user_passes_test(lambda u: u.is_staff)
def info_edit_lienholder(request, id, leinholderId):
    """
    Add a lienholder to a lien.

    Params:
        id: refers to the id of the lien
        *lienholder: the lienholder id, so that we can auto-fill those fields
    """
    lien = get_object_or_404(Lien, pk=id)

    lienHolder = get_object_or_404(LienHolder, pk=leinholderId);

    infoForm = InfoEditLienholderForm(request.POST or None, instance=lienHolder);

    if request.POST and infoForm.is_valid():
        infoForm.save();

        return redirect("/lien/info/"+id);

    

    initial = {
        "lien": lien
    }
    # if request.POST :
        # return render_to_response('lien/info.html', template_map)
    # elif request.POST:
        
    #     # User wants to create new lienholder
    #     new_lienholder = LienHolder(lien=lien)
    #     form_data =request.POST.dict()
    #     lienholder_form = InfoAddLienholderForm(
    #         form_data,
    #         instance=new_lienholder
    #     )
    #     if lienholder_form.is_valid():
    #         lienholder_form.save()
    #     return redirect('lien-view_info', id)
    # else:
    #     template_map["form"] = AddLienholderForm(initial)
    #     return render_to_response('lien/info.html', template_map)




@user_passes_test(lambda u: u.is_staff)
def add_lienholder(request, id, *leinholderId):
    """
    Add a lienholder to a lien.

    Params:
        id: refers to the id of the lien
        *lienholder: the lienholder id, so that we can auto-fill those fields
    """

    lien = get_object_or_404(Lien, pk=id)
    initial = {
        "lien": lien
    }
    template_map = {
        "id": id,
        "lien": lien,
    }
    if request.POST and 'lienholder-search-input' in request.POST:
        # User wants to autocomplete form fields
        search_query = request.POST['lienholder-search-input']
        # Get the matching lienholder, if any
        search_results = LienHolder.objects.filter(name__icontains=search_query)
        lienholder = search_results[0] if search_results else None
        # Populate lienholder features so that it shows up in the view
        if lienholder:
            template_map['lienholder'] = lienholder
            initial["name"] = lienholder.name
            initial["address"] = lienholder.address
            initial["address2"] = lienholder.address2
            initial["city"] = lienholder.city
            initial["state"] = lienholder.state
            initial["phone"] = lienholder.phone
            initial["zip"] = lienholder.zip
        else:
            template_map["none_found"] = True
        template_map["form"] = InfoAddLienholderForm(initial)
        return render_to_response('lien/add_lienholder.html', template_map)
    elif request.POST:
        # User wants to create new lienholder
        new_lienholder = LienHolder(lien=lien)
        form_data =request.POST.dict()
        lienholder_form = InfoAddLienholderForm(
            form_data,
            instance=new_lienholder
        )
        if lienholder_form.is_valid():
            new_lienholder = lienholder_form.save()
            messages.add_message(request, messages.SUCCESS, 'Lienholder Successfully Added. Add another Lienholder if you need.')

            # We need to add a tracker here
            activity.create_add_log(
                user = request.user,
                lien = lien,
                object_id = new_lienholder.id,
                object_type = "Lienholder"

            )
            
            return redirect('lien-add_lienholder', id)
        else:
            template_map["form"] = lienholder_form
            messages.add_message(request, messages.WARNING, 'Sorry. Not all the information was available and Lienholder was not added.')
            # return render_to_response('lien/add_lienholder.html', template_map)
            return redirect('lien-add_lienholder', id)
    else:
        template_map["first_load"] = True
        template_map["form"] = InfoAddLienholderForm(initial)

        return render(request, 'lien/add_lienholder.html', template_map)

@user_passes_test(lambda u: u.is_staff)
def create_lienholder_for_lien(request, lienId):
    """
    Create a lienholder attached to a lien. Redirect user to the
    lien detail page.
    """
    if not request.POST:
        raise Exception(
            'This view is only for creating a new lienholder with post request'
        )


@user_passes_test(lambda u: u.is_staff)
def generate_letters_batch(request, dateFrom, dateTo, letterType):
    '''
    Generates letters between the dates given in the dateRange dict.

    Params:
        dateFrom and dateTo: all liens between these dates will be used. Expects a
            string in the format of '%Y-%m-%d'.
        letterType is, e.g., 'payoff_letter'. For types, see document templates
            in `liendata/lien/templates/document/letter/`. Note that `.html` is
            omitted.
    '''
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

    counties = request.GET.get('counties', None)
    # Get our dates
    liens_in_date_range = getLiensForLetter(
        dateFrom, dateTo, letterType, {'counties': [counties]} if counties != 'None' else {})
    
    from utilities.letters_noimports import divideByDueDate
    today = date.today().strftime('%Y-%m-%d')

    # print liens that could be sent.
    lettersByDueStatus = { letterType : divideByDueDate('1990-01-01',today,letterType, {'counties': [counties]} if counties != 'None' else {}) }
    liens_in_date_range = lettersByDueStatus[letterType]['available']
    
    num_total_liens = len(liens_in_date_range)
    # We require more filtering, letter four check prelit_fees. may need to update this to filter with Decimal class?
    if(letterType == 'letter_four'):
        def filter_prelit(lien):
            dec = Decimal(526)
            if(dec.compare(lien.prelit_fees) != 1):
                return True
            return False

        
        liens_in_date_range = filter(filter_prelit, liens_in_date_range)
    
    paginator = Paginator(liens_in_date_range, 100)
    
    page = request.GET.get('page')
    

    try:
        liens_to_print = paginator.page(page)
    except PageNotAnInteger:
        liens_to_print = paginator.page(1)
    except EmptyPage:
        liens_to_print = paginator.page(paginator.num_pages)
    
    # We can't print 100,000 liens at a time!
    # liens_to_print = take(100, liens_in_date_range)

    num_liens_to_print = len(liens_to_print)
    letter_template_str =  'document/letter/%s.html' % letterType
    lien_ids_json = json.dumps([l.id for l in liens_to_print])
    # Render Letter
    return render_to_response(
        'document/letter/batch_letters.html', {
            'liens': liens_to_print,
            'lien_ids_json': lien_ids_json,
            'num_total_liens': num_total_liens,
            'num_liens_to_print': num_liens_to_print,
            'letter_template_str': letter_template_str,
            'letter_type': '%s' % letterType,
            'county': counties
        }
    )

@user_passes_test(lambda u: u.is_staff)
def generate_letters(request):
    '''
    Allows users to select which letters they wish to generate.
    '''
    supportedLetterTypes = [
        ['letter_one', 'First Letter'],
        ['letter_two', 'Second Letter'],
        ['foreclosure_warning_letter', 'Foreclosure Warning'],
        ['occupant_letter', 'Occupant Letter'],
    ]
    if not request.POST:
        return render_to_response(
            'lien/generate_letters.html', {
                'letterTypes': supportedLetterTypes
            }
        )
    else:
        dateFrom = request.POST['date-from']
        dateTo = request.POST['date-to']
        letterType = request.POST['letter-type']
        return HttpResponseRedirect(
            reverse(
                'generate-letters-batch',
                args = (dateFrom, dateTo, letterType)
            )
        )

@user_passes_test(lambda u: u.is_staff)
def complaint_letter_review(request, id):
    '''
    Allows user to see complaint letter data
    Displays form with missing necessary data highlighted 
    Provides print button so user can preview and then print letter
    '''

    lien = get_object_or_404(Lien, pk=id)
    complaint_letter_total = lien.lien_amount + lien.total_interest + lien.admin_fee + lien.get_attorney_fee
    

    context = {
        'lien': lien,
        'complaint_letter_total': complaint_letter_total,
        'attorney': settings.ATTORNEY,
    }
    
    return render(request, 'lien/complaint_letter_review.html', context)

@user_passes_test(lambda u: u.is_staff)
def primary_status_edit_and_update(request):
    '''
    Display list of liens with statuses that need to be updated because
    the status is being removed from list.
    '''
    
    # Total
    all_liens = Lien.objects.all().count()

    # Primary statuses
    new_primary = [74, 75, 76]
    primary_orphaned = Lien.objects.exclude(status__in=new_primary).count()
    primary_set = Lien.objects.filter(status__in=new_primary).count()
    primary_total = primary_orphaned + primary_set
    primary_orphaned_liens = Lien.objects.exclude(status__in=new_primary)

    # Secondary statuses
    new_secondary = [1,24,3,44,5,60,61,45,42,43]
    secondary_orphaned = Lien.objects.exclude(status__in=new_secondary).count()
    secondary_set = Lien.objects.filter(status__in=new_secondary).count()
    secondary_total = secondary_orphaned + secondary_set

    # Third statuses
    new_third = [38,49,50,35,47,51,52,53,54,55,56,48,57,16,59,58]
    third_orphaned = Lien.objects.exclude(status__in=new_third).count()
    third_set = Lien.objects.filter(status__in=new_third).count()
    third_total = third_orphaned + third_set

    #paid_in_full
    paid_in_full = Lien.objects.filter(status=1).count()
    paid_in_full_secondary = Lien.objects.filter(second_status=60).count()

    #bankruptcy
    bankruptcy = Lien.objects.filter(status=11).count()
    bankruptcy_secondary = Lien.objects.filter(second_status=5).count()

    #litigation
    litigation = Lien.objects.filter(status=12).count()
    litigation_secondary = Lien.objects.filter(second_status=3).count()

    #foreclosure
    foreclosure = Lien.objects.filter(status=27).count()
    foreclosure_secondary = Lien.objects.filter(second_status=44).count()

    context = {
        'all_liens': all_liens,
        'primary_orphaned_liens': primary_orphaned_liens,
        'primary_orphaned': primary_orphaned,
        'primary_set': primary_set,
        'primary_total': primary_total,
        'secondary_orphaned': secondary_orphaned,
        'secondary_set': secondary_set,
        'secondary_total': secondary_total,
        'third_orphaned': third_orphaned,
        'third_set': third_set,
        'third_total': third_total,
        'paid_in_full': paid_in_full,
        'paid_in_full_secondary': paid_in_full_secondary,
        'bankruptcy': bankruptcy,
        'bankruptcy_secondary': bankruptcy_secondary,
        'litigation': litigation, 
        'litigation_secondary': litigation_secondary,
        'foreclosure': foreclosure,
        'foreclosure_secondary': foreclosure_secondary
    }
    return render_to_response('lien/primary_status_edit_and_update.html', context )
        
@user_passes_test(lambda u: u.is_staff)
def dnb_status(request, id):
    lien = get_object_or_404(Lien, pk=id) # Gets the lien from the id
    doNotBuy = False
    
    if lien.dnb == False:
        doNotBuy = True
    else:
        doNotBuy = False
    
    setattr(lien, 'dnb', doNotBuy)
    lien.save()
    
    liens_w_mapno = Lien.objects.filter(
        map_number=lien.map_number,
        county = lien.county
    )
    # Remove duplicate liens
    other_liens = [
        l for l in liens_w_mapno
        if l != lien
    ]


    for l in other_liens:
        if l.dnb == False:
            doNotBuy = True
        else: 
            doNotBuy = False
        setattr(l, 'dnb', doNotBuy)
        l.save()
    
    return HttpResponseRedirect(reverse('lien-view', args = [id,]))


@user_passes_test(lambda u: u.is_staff)
def refund_requested_status(request, id):
    lien = get_object_or_404(Lien, pk=id) # Gets the lien from the id
    refundRequested = False

    today = datetime.today().strftime('%Y-%m-%d');

    if lien.refund_requested == False:
        refundRequested = True;
        lien.refund_requested_date = today;
        
    else:
        refundRequested = False;


    setattr(lien, 'refund_requested', refundRequested)
    lien.save()


    # TODO: Maybe add associated liens? need to ask


    return HttpResponseRedirect(reverse('lien-view', args = [id,]))

@user_passes_test(lambda u: u.is_staff)
def property_purchase_status(request, id):
    lien = get_object_or_404(Lien, pk=id) # Gets the lien from the id
    propertyPurchased = False

    if lien.property_purchased == False:
        propertyPurchased = True;
    else:
        propertyPurchased = False;

    setattr(lien, 'property_purchased', propertyPurchased)
    lien.save()

    return HttpResponseRedirect(reverse('lien-view', args = [id,]))

@user_passes_test(lambda u: u.is_staff)
def special_asset_status(request, id):
    lien = get_object_or_404(Lien, pk=id) # Gets the lien from the id
    specialAsset = False

    if lien.special_asset == False:
        specialAsset = True;
    else:
        specialAsset = False;

    setattr(lien, 'special_asset', specialAsset)
    lien.save()

    return HttpResponseRedirect(reverse('lien-view', args = [id,]))



@user_passes_test(lambda u: u.is_staff)
def structure_only_status(request, id):
    lien = get_object_or_404(Lien, pk=id) # Gets the lien from the id
    structureOnly = False

    if lien.structure_only == False:
        structureOnly= True;
    else:
        structureOnly = False;

    setattr(lien, 'structure_only', structureOnly)
    lien.save()

    return HttpResponseRedirect(reverse('lien-view', args = [id,]))



# THIS IS THE WAY IT SHOULD BE DONE FROM NOW ON!!!!!!!!!
@user_passes_test(lambda u: u.is_staff)
def change_status_bubble(request, id, status, field):
    lien = get_object_or_404(Lien, pk=id) # Gets the lien from the id


    # Default it
    statusChanged = False
    if status == 'False':
        statusChanged = True
    else:
        statusChanged = False


    # Save field
    setattr(lien, str(field), statusChanged)
    lien.save()





    # Associated liens
    liens_w_mapno = Lien.objects.filter(
        map_number=lien.map_number,
        county = lien.county
    )
    # Remove duplicate liens
    other_liens = [
        l for l in liens_w_mapno
        if l != lien
    ]


    for l in other_liens:
        setattr(l, str(field), statusChanged)
        l.save()


    return HttpResponseRedirect(reverse('lien-view', args = [id,]))





@user_passes_test(lambda u: u.is_staff)
def rep_by_attorney_status(request, id):
    lien = get_object_or_404(Lien, pk=id) # Gets the lien from the id
    rep_by_attorney = False

    if lien.rep_by_atty == False:
        rep_by_attorney= True;
    else:
        rep_by_attorney = False;

    setattr(lien, 'rep_by_atty', rep_by_attorney)
    lien.save()

    return HttpResponseRedirect(reverse('lien-view', args = [id,]))


@user_passes_test(lambda u: u.is_staff)
def order_title_status(request, id):
    lien = get_object_or_404(Lien, pk=id) # Gets the lien from the id
    titleOrdered = False

    if lien.order_title == False:
        titleOrdered = True;
    else:
        titleOrdered = False;


    setattr(lien, 'order_title', titleOrdered)
    lien.save()


    # Associated liens
    liens_w_mapno = Lien.objects.filter(
        map_number=lien.map_number,
        county = lien.county
    )
    # Remove duplicate liens
    other_liens = [
        l for l in liens_w_mapno
        if l != lien
    ]


    for l in other_liens:
        setattr(l, 'order_title', titleOrdered)
        l.save()

    return HttpResponseRedirect(reverse('lien-view', args = [id,]))

@user_passes_test(lambda u: u.is_staff)
def bad_address_status(request, id):
    addAssociated = request.POST.get('add-address-associated', None)
    lien = get_object_or_404(Lien, pk=id) # Gets the lien from the id

    badAddress = False

    if lien.bad_address == False:
        badAddress = True
    else:
        badAddress = False;

    
    setattr(lien, 'bad_address', badAddress)
    messages.add_message(request, messages.SUCCESS, 'Bad Address has been changed successfully.')
    lien.save()


    if addAssociated == 'yes':
        # Associated liens
        liens_w_mapno = Lien.objects.filter(
            map_number=lien.map_number,
            county = lien.county
        )
        # Remove duplicate liens
        other_liens = [
            l for l in liens_w_mapno
            if l != lien
        ]

        for l in other_liens:
            setattr(l, 'bad_address', badAddress)
            l.save()



    return HttpResponseRedirect(reverse('lien-view', args = [id,]))



@user_passes_test(lambda u: u.is_staff)
def woa_status(request, id):
    lien = get_object_or_404(Lien, pk=id) # Gets the lien from the id

    isWoa = False

    if lien.woa == False:
        isWoa = True
    else:
        isWoa = False;

    
    setattr(lien, 'woa', isWoa)
    messages.add_message(request, messages.SUCCESS, 'WOA has been changed successfully.')
    lien.save()

    liens_w_mapno = Lien.objects.filter(
        map_number=lien.map_number,
        county = lien.county
    )
    # Remove duplicate liens
    other_liens = [
        l for l in liens_w_mapno
        if l != lien
    ]

    for l in other_liens:
        setattr(l, 'woa', isWoa)
        l.save()
        


    return HttpResponseRedirect(reverse('lien-view', args = [id,]))

@user_passes_test(lambda u: u.is_staff)
def payment_plan_toggle(request, id):
    lien = get_object_or_404(Lien, pk=id)
    on_payment_plan = False

    if lien.payment_plan == False:
        on_payment_plan = True
    else:  
        on_payment_plan = False

    setattr(lien, 'payment_plan', on_payment_plan)
    lien.save()

    return HttpResponseRedirect(reverse('lien-view', args = [id,]))


@user_passes_test(lambda u: u.is_staff)
def bad_liens_report(request):

    all_primary = [74, 76, 75]

    missing_actual_cost_liens_count = Lien.objects.filter(
    Q(actual_cost__isnull=True)
    ).count()

    missing_alternate_date_purchased_count = Lien.objects.filter(Q(alternate_date_purchased__isnull=True)).count()
    missing_purchased_from_count = Lien.objects.filter(Q(purchased_from__isnull=True)).count()

    lienholders = LienHolder.objects.filter(Q(mortgage_book_page_number__exact=''))
    lienholders_missing_book_page_count = lienholders.count()
    lienholders = LienHolder.objects.filter(Q(category__isnull=True))
    lienholders_missing_category_count = lienholders.count()

    bad_status_liens = Lien.objects.exclude(status__in=all_primary)
    bad_status_liens_count = bad_status_liens.count()

    success = 0

    context = {
        'missing_actual_cost_liens_count': missing_actual_cost_liens_count,
        'missing_alternate_date_purchased_count': missing_alternate_date_purchased_count,
        'missing_purchased_from_count': missing_purchased_from_count,
        'lienholders_missing_book_page_count': lienholders_missing_book_page_count,
        'lienholders_missing_category_count': lienholders_missing_category_count,
        'bad_status_liens_count': bad_status_liens_count,
        'success': success
    }


    return render(request, 'lien/bad_liens.html', context);



@user_passes_test(lambda u: u.is_staff)
def missing_actual_cost_view(request):

    liens = Lien.objects.filter(
    Q(actual_cost__isnull=True)
    )

    count = liens.count()

    context = {
        'liens': liens,
        'count': count,
    }

    return render(request, 'bad_lien/missing_actual_cost.html', context);

@user_passes_test(lambda u: u.is_staff)
def missing_alternate_date_purchased(request):

    liens = Lien.objects.filter(Q(alternate_date_purchased__isnull=True))

    count = liens.count()

    context = {
        'liens': liens,
        'count': count,
    }

    return render(request, 'bad_lien/missing_alternate_date_purchased.html', context);

@user_passes_test(lambda u: u.is_staff)
def missing_purchased_from(request):

    liens = Lien.objects.filter(Q(purchased_from__isnull=True))

    count = liens.count()

    context = {
        'liens': liens,
        'count': count,
    }

    return render(request, 'bad_lien/missing_purchased_from.html', context);

@user_passes_test(lambda u: u.is_staff)
def lienholders_missing_book_and_page(request):

    lienholders = LienHolder.objects.filter(Q(mortgage_book_page_number__exact=''))
    
    count = lienholders.count()

    context = {
        'lienholders': lienholders,
        'count': count,
    }

    return render(request, 'bad_lien/lienholder_missing_book_and_page.html', context);

@user_passes_test(lambda u: u.is_staff)
def lienholders_missing_category(request):

    lienholders = LienHolder.objects.filter(Q(category__isnull=True))
    
    count = lienholders.count()

    context = {
        'lienholders': lienholders,
        'count': count,
    }

    return render(request, 'bad_lien/lienholder_missing_category.html', context);

@user_passes_test(lambda u: u.is_staff)
def bad_primary_status(request):

    all_primary = [74, 76, 75]
    liens = Lien.objects.exclude(status__in=all_primary)
    count = liens.count()

    context = {
        'liens': liens,
        'count': count,
    }

    return render(request, 'bad_lien/bad_primary_status.html', context);



@user_passes_test(lambda u: u.is_staff)
def edit_bad_lienholder_view(request, lienholder_id, lien_id):
    """
    Edit Lienholder
    """
    lien = get_object_or_404(Lien, pk=lien_id)
    lienholder = get_object_or_404(LienHolder, pk=lienholder_id)

    if request.method == "POST":
        form = InfoAddLienholderForm(request.POST, instance=lienholder)
        if form.is_valid():
            form.save()

            activity.create_update_log(
                lien = lien,
                user = request.user,
                object_id = lienholder_id,
                object_revision_id = lienholder_id,
                object_type = "Lienholder"
            )
            
            return redirect('lien-add_lienholder', id=lien.id)

    else:
        form = InfoAddLienholderForm(instance=lienholder)

    return render(request, 'edit/edit_lienholder.html', { 'form': form, 'lienholder': lienholder, 'lien': lien } )


@user_passes_test(lambda u: u.is_staff)
def edit_service_date_view(request, lienholder_id, lien_id):
    """
    Edit Lienholder
    """
    lien = get_object_or_404(Lien, pk=lien_id)
    lienholder = get_object_or_404(LienHolder, pk=lienholder_id)

    if request.method == "POST":
        form = ForeclosureLienholderForm(request.POST, instance=lienholder)
        if form.is_valid():
            form.save()
            return redirect('lien.edit_foreclosure', id=lien.id)

    else:
        form = ForeclosureLienholderForm(instance=lienholder)

    return render(request, 'edit/edit_service_date_lienholder.html', { 'form': form, 'lienholder': lienholder, 'lien': lien } )


@user_passes_test(lambda u: u.is_staff)
def add_notification_view(request, id):
    """
    Add Task to the Notification report manager.
    """
    lien = get_object_or_404(Lien, pk=id)

    now = datetime.now()
# now.strftime("%m/%d/%Y %I:%M:%S %p")
    form = AddNotificationForm(initial={
        'creator': request.user,
        'lien': id,
        'timestamp': now,
        'status': 'not_complete'
    })

    if request.method == "POST":
        form = AddNotificationForm(request.POST)
        
        if form.is_valid():
            newTask = form.save()

            taskNote = form.cleaned_data['description']
            
            # Lets make a note when a task is created
            creator = form.cleaned_data['creator']
            creator = creator.first_name +" "+creator.last_name
            
            recipients = form.cleaned_data['notification_group']
            recipLength = len(recipients)
            recipString = ""

            i = 1;
            for r in recipients:
                # This will mean its the last in the list- so no comma
                if i == recipLength:
                    recipString += r.first_name+ " "+r.last_name    
                else:
                    recipString += r.first_name+ " "+r.last_name+", "
                i += 1

            

            fullString = creator+" assigned '"+taskNote+"' task to "+recipString
            Note.objects.create(body=fullString, user = request.user, lien=lien)

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
            
            if len(other_liens) > 0:
                isMultiple = True
            else:
                isMultiple = False
                
            if isMultiple:
                associatedLienString = " on associated account #"+str(lien.id)
                for l in other_liens:
                    Note.objects.create(body=fullString+associatedLienString, user = request.user, lien=l)



        return redirect('lien-view', lien.id)          
    return render(request, 'lien/forms/add_notification_form.html', { 'form': form, 'lien': lien })

@user_passes_test(lambda u: u.is_staff)
def edit_foreclosure_view(request, id):
    """
    Edit Foreclosure Information
    """
    lien = get_object_or_404(Lien, pk=id)
    # lienholder = get_object_or_404(LienHolder, lien_id=lien.id)
    lienholder = LienHolder.objects.filter(lien_id = lien.id)
    isMultiple = False;
    otherLiens = get_other_liens(lien, lien.id);

    if len(otherLiens) > 0:
        isMultiple = True;

    if request.method == "POST": 
        form = EditForeclosureForm(request.POST, instance=lien)
        if form.is_valid():

            for lh in lienholder:
                test = request.POST.get(str(lh.id), None)

            # If we want to add to the associated liens
            handleMultipleAc = request.POST.get('add-associated-fc-prompt', None)
            if handleMultipleAc and handleMultipleAc == 'yes':
                otherLiens = get_other_liens(lien, lien.id)
                for l in otherLiens:
                    newForm = EditForeclosureForm(request.POST, instance=l)
                    newForm.save();



            form.save()
            return redirect('lien-view', lien.id)

    else:
        form = EditForeclosureForm(instance=lien)
        # lienholderForm = ForeclosureLienholderForm(instance=lienholder)
        
    return render(request, 'edit/edit_foreclosure.html', { 'form': form, 'lien': lien, 
    'is_multiple': isMultiple })


@user_passes_test(lambda u: u.is_staff)
def edit_attorney_info_view(request, id):
    """
    Edit Foreclosure Information
    """
    lien = get_object_or_404(Lien, pk=id)

    lienAttorney = lien.attorney.id;

    attorney = get_object_or_404(Attorney, pk=lienAttorney);

    if request.method == "POST": 
        form = EditAttorneyInfoForm(request.POST, instance=lien)
        if form.is_valid():
            form.save()
            return redirect('lien-view', lien.id)

    else:
        form = EditAttorneyInfoForm(instance=lien)
        
    return render(request, 'edit/edit_attorney_info.html', { 'form': form, 'lien': lien, 'attorney': attorney })

@user_passes_test(lambda u: u.is_staff)
def edit_property_info_view(request, id):
    """
    Edit Foreclosure Information
    """
    lien = get_object_or_404(Lien, pk=id)
    isMultiple = False;
    otherLiens = get_other_liens(lien, lien.id);

    if len(otherLiens) > 0:
        isMultiple = True;

    if request.method == "POST": 
        form = EditPropertyInfoForm(request.POST, instance=lien)
        if form.is_valid():
            
            # If we want to add to the associated liens
            handleMultipleAc = request.POST.get('add-associated-prompt', None)
            if handleMultipleAc and handleMultipleAc == 'yes':
                otherLiens = get_other_liens(lien, lien.id)
                for l in otherLiens:
                    newForm = EditPropertyInfoForm(request.POST, instance=l)
                    newForm.save();
            
            # Save initial lien
            form.save()
            return redirect('lien-view', lien.id)

    else:
        form = EditPropertyInfoForm(instance=lien)
        
    return render(request, 'edit/edit_property_info.html', { 'form': form, 'lien': lien, 'is_multiple': isMultiple })


@user_passes_test(lambda u: u.is_staff)
def edit_current_owner_view(request, id):
    """
    Edit Foreclosure Information
    """
    lien = get_object_or_404(Lien, pk=id)
    isMultiple = False;
    otherLiens = get_other_liens(lien, lien.id);

    if len(otherLiens) > 0:
        isMultiple = True;

    if request.method == "POST": 
        form = EditCurrentOwnerFullForm(request.POST, instance=lien)
        if form.is_valid():
            
            # If we want to add to the associated liens
            handleMultipleAc = request.POST.get('add-associated-prompt', None)
            if handleMultipleAc and handleMultipleAc == 'yes':
                otherLiens = get_other_liens(lien, lien.id)
                for l in otherLiens:
                    newForm = EditCurrentOwnerFullForm(request.POST, instance=l)
                    newForm.save();
            
            # Save initial lien
            form.save()
            return redirect('lien-view', lien.id)

    else:
        form = EditCurrentOwnerFullForm(instance=lien)
        
    return render(request, 'edit/edit_current_owner.html', { 'form': form, 'lien': lien, 'is_multiple': isMultiple })

@user_passes_test(lambda u: u.is_staff)
def edit_current_owner_info(request, id):
    """
    Edit Current Owner Information
    """
    lien = get_object_or_404(Lien, pk=id)

    if request.method == "POST": 
        form = EditCurrentOwnerForm(request.POST)
        if form.is_valid():
            lien.current_owner_phone1 = form.cleaned_data['current_owner_phone1']
            lien.current_owner_phone2 = form.cleaned_data['current_owner_phone2']
            lien.save()
            return redirect('lien-view', lien.id)

        return HttpResponseRedirect(reverse('lien-view', args = [id,]))
    return HttpResponseRedirect(reverse('lien-index'))

@user_passes_test(lambda u: u.is_staff)
def status_list_view(request, id):
    """
    Get list of liens for a specific status
    """
    liens = Lien.objects.filter(status=id)

    if not liens:
        status_title = 'No liens in this status'
    else:
        status_title = liens[0].status

    count = liens.count()

    context = {
        'liens': liens,
        'count': count,
        'status_title': status_title,
    }

    return render(request, 'lien/status_list_view.html', context);

@user_passes_test(lambda u: u.is_staff)
def second_status_list_view(request, id):
    """
    Get list of liens for a specific status
    """
    liens = Lien.objects.filter(second_status=id)

    if not liens:
        status_title = 'No liens in this status'
    else:
        status_title = liens[0].second_status

    count = liens.count()

    context = {
        'liens': liens,
        'count': count,
        'status_title': status_title,
    }

    return render(request, 'lien/second_status_list_view.html', context);

@user_passes_test(lambda u: u.is_staff)
def third_status_list_view(request, id):
    """
    Get list of liens for a specific status
    """
    liens = Lien.objects.filter(third_status=id)

    if not liens:
        status_title = 'No liens in this status'
    else:
        status_title = liens[0].third_status

    count = liens.count()

    context = {
        'liens': liens,
        'count': count,
        'status_title': status_title,
    }

    return render(request, 'lien/third_status_list_view.html', context);

def getAssociatedLiens(lien):
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


@user_passes_test(lambda u: u.is_staff)
def modify_lien(request):
    '''
    An endpoint to POST modifications of liens to.

    Not every field should be mutable, only those in
    `mutable_fields` below
    '''
    # A list of the fields
    mutable_fields = (
        'master_commissioner_sale_date',
        'paid_in_full',
        'woa_required', 
        'date_filed_stamped',
        'date_default_letter_mailed',
        'other_amounts_owed',
        'date_last_party_served',
        'date_motion_for_distribution_filed',
        'date_poc_filed',
        'date_of_discharge',
        'date_of_dismissed',
        'date_of_service',
        'date_of_last_service',
        'pva_card',
        'pva_year',
        'date_title_ordered'
    )

    associated_bill_fields = (
        'mc_sale_date',
    )
    required_json_fields = (
        'field_to_mutate',
        'val_to_set',
        'lien_id'
    )
    # Check to see if it's a POST request
    if request.method != 'POST':
        response = simplejson.dumps({
            'success': False,
            'msg': 'Not a post request'
        })
        return HttpResponse(response, mimetype="application/json")
    # Parse body
    try:
        post_dict = json.loads(request.body, parse_float=Decimal)
    except Exception as e:
        response = simplejson.dumps({
            'success': False,
            'msg': 'Unable to parse JSON body.'
        })
        return HttpResponse(response, mimetype="application/json")
    # Validate body
    if not all([lambda x: x in required_json_fields for x in post_dict.keys()]):
        msg = "Missing required a required fields. Req'd fields: {req}. Given fields {given}".format(
            req=required_json_fields,
            given=[x for x in post_dict.keys()]
        )
        response = simplejson.dumps({
            'success': False,
            'msg': msg
        })
        return HttpResponse(response, mimetype="application/json")

    # Change the field on the lien
    try:
        lien = get_object_or_404(Lien, pk=post_dict['lien_id'])
        setattr(lien, post_dict['field_to_mutate'], post_dict['val_to_set'])
        lien.save()

        # associated bill fields need to save the value to those associated as well
        if post_dict['field_to_mutate'] in associated_bill_fields:
            otherLiens = getAssociatedLiens(lien)
            if otherLiens:
                for l in otherLiens:
                    setattr(l, post_dict['field_to_mutate'], post_dict['val_to_set'])
                    l.save()

        json_response = simplejson.dumps({
            'success': True,
            'msg': 'Success setting value {v} on lien id {id}'.format(
                v=post_dict['val_to_set'],
                id=post_dict['lien_id']
            )
        })
        return HttpResponse(json_response, mimetype="application/json")
    except Exception as e:
        json_response = simplejson.dumps({
            'success': False,
            'msg': 'Error setting lien value %s' % e
        })
        return HttpResponse(json_response, mimetype="application/json")

# @user_passes_test(lambda u: u.is_staff)
def update_inspection_note(request):
    '''
    An endpoint to POST InspectionNote
    '''    
    # Check to see if it's a POST request
    if request.method != 'POST':
        response = simplejson.dumps({
            'success': False,
            'msg': 'Not a post request'
        })
        return HttpResponse(response, mimetype="application/json")
    # Parse body
    try:
        post_dict = json.loads(request.body, parse_float=Decimal)
    except Exception as e:
        response = simplejson.dumps({
            'success': False,
            'msg': 'Unable to parse JSON body.'
        })
        return HttpResponse(response, mimetype="application/json")

    # Change the field on the lien
    try:
        lien = get_object_or_404(Lien, pk=post_dict['lien_id'])
        note = post_dict['note']
        inspectionNote = InspectionNote.objects.create(body=note, lien_id=lien.id)
        json_response = simplejson.dumps({
            'success': True,
            'msg': 'Success creating inspection note'
        })
        return HttpResponse(json_response, mimetype="application/json")
    except Exception as e:
        json_response = simplejson.dumps({
            'success': False,
            'msg': 'Error creating inspection note %s' % e
        })
        return HttpResponse(json_response, mimetype="application/json")




def export_field_select(request):

    if request.method == 'POST':

        form = DateSearchForm(request.GET)

        if form.is_valid():

            if not form.cleaned_data['from_date'] or not form.cleaned_data['to_date']:
                if form.cleaned_data['date_field'] != 'no_date':
                    liens = Lien.objects.filter(**{
                        '%s__isnull' % form.cleaned_data['date_field']: True,
                    })
                else:
                    liens = Lien.objects.all()
            else:
                liens = Lien.objects.date_search(form.cleaned_data['from_date'], form.cleaned_data['to_date'],
                                                 form.cleaned_data['date_field'])
            if form.cleaned_data['investor']:
                liens = liens.filter(investor=form.cleaned_data['investor'])

            if form.cleaned_data['county']:
                liens = liens.filter(county=form.cleaned_data['county'])

            if form.cleaned_data['status']:
                liens = liens.filter(status=form.cleaned_data['status'])

            if form.cleaned_data['second_status']:
                liens = liens.filter(second_status=form.cleaned_data['second_status'])

            if form.cleaned_data['third_status']:
                liens = liens.filter(third_status=form.cleaned_data['third_status'])

            if form.cleaned_data['paid_status'] == 'paid':
                liens = liens.filter(date_paid__isnull=False)
            elif form.cleaned_data['paid_status'] == 'unpaid':
                liens = liens.filter(date_paid__isnull=True)

            if form.cleaned_data['action_date']:
                liens = liens.filter(action_date=form.cleaned_data['action_date'])

            if form.cleaned_data['lien_owner']:
                liens = liens.filter(lien_owner=form.cleaned_data['lien_owner'])

            if form.cleaned_data['purchased_from']:
                liens = liens.filter(purchased_from_new=form.cleaned_data['purchased_from'])

            if form.cleaned_data['tax_year'] != 'any':
                liens = liens.filter(tax_year=int(form.cleaned_data['tax_year']))

            if form.cleaned_data['ci_number']:
                ci_number = form.cleaned_data['ci_number'];
                if 'CI' not in ci_number and 'ci' not in ci_number:
                    ci_number = 'CI-' + ci_number;

                # Search the notes, excluding liens from above
                liens = liens.filter(
                    Q(note__body__icontains=ci_number)
                )
            if form.cleaned_data['street_address']:
                street_address = form.cleaned_data['street_address']
                liens = liens.filter(
                    Q(owner_address__icontains=street_address) | \
                    Q(owner_address2__icontains=street_address) | \
                    Q(current_owner_address__icontains=street_address) | \
                    Q(current_owner_address2__icontains=street_address) | \
                    Q(property_location__icontains=street_address)
                )

            selectedFields = [];

            selected = request.POST;

            for s in selected:
                selectedFields.append(s);

            query = urllib.urlencode(request.GET)

            return render_or_export('lien/search.html', {'liens': liens, 'query': query}, request, selectedFields)


    elif request.method == 'GET':
        form = DateSearchForm(request.GET)

        if form.is_valid():

            if not form.cleaned_data['from_date'] or not form.cleaned_data['to_date']:
                if form.cleaned_data['date_field'] != 'no_date':
                    liens = Lien.objects.filter(**{
                        '%s__isnull' % form.cleaned_data['date_field']: True,
                    })
                else:
                    liens = Lien.objects.all()
            else:
                liens = Lien.objects.date_search(form.cleaned_data['from_date'], form.cleaned_data['to_date'],
                                                 form.cleaned_data['date_field'])
            if form.cleaned_data['investor']:
                liens = liens.filter(investor=form.cleaned_data['investor'])

            if form.cleaned_data['county']:
                liens = liens.filter(county=form.cleaned_data['county'])

            if form.cleaned_data['status']:
                liens = liens.filter(status=form.cleaned_data['status'])

            if form.cleaned_data['second_status']:
                liens = liens.filter(second_status=form.cleaned_data['second_status'])

            if form.cleaned_data['third_status']:
                liens = liens.filter(third_status=form.cleaned_data['third_status'])

            if form.cleaned_data['paid_status'] == 'paid':
                liens = liens.filter(date_paid__isnull=False)
            elif form.cleaned_data['paid_status'] == 'unpaid':
                liens = liens.filter(date_paid__isnull=True)

            if form.cleaned_data['action_date']:
                liens = liens.filter(action_date=form.cleaned_data['action_date'])

            if form.cleaned_data['lien_owner']:
                liens = liens.filter(lien_owner=form.cleaned_data['lien_owner'])

            if form.cleaned_data['purchased_from']:
                liens = liens.filter(purchased_from_new=form.cleaned_data['purchased_from'])

            if form.cleaned_data['tax_year'] != 'any':
                liens = liens.filter(tax_year=int(form.cleaned_data['tax_year']))

            if form.cleaned_data['ci_number']:
                ci_number = form.cleaned_data['ci_number'];
                if 'CI' not in ci_number and 'ci' not in ci_number:
                    ci_number = 'CI-' + ci_number;

                # Search the notes, excluding liens from above
                liens = liens.filter(
                    Q(note__body__icontains=ci_number)
                )
            if form.cleaned_data['street_address']:
                street_address = form.cleaned_data['street_address']
                liens = liens.filter(
                    Q(owner_address__icontains=street_address) | \
                    Q(owner_address2__icontains=street_address) | \
                    Q(current_owner_address__icontains=street_address) | \
                    Q(current_owner_address2__icontains=street_address) | \
                    Q(property_location__icontains=street_address)
                )
            # If there is only one result, redirect to that result
            #if len(liens) == 1:
            #    return HttpResponseRedirect(reverse('lien-view', args = [liens[0].id]))

            query = urllib.urlencode(request.GET)

            allFields = Lien._meta.get_all_field_names();

            modifiedAllFields = [];

            for a in allFields:
                if 'lienholder' not in a or 'payment' not in a:
                    modifiedAllFields.append(a);

        return render(request, 'lien/export_field_select.html', {'liens': liens, 'allFields' : modifiedAllFields});

@user_passes_test(lambda u: u.is_staff)
def dictionary(request):    
    return render(request, 'lien/dictionary_and_terms.html', {})






@user_passes_test(lambda u: u.is_staff)
def change_lienholder_services(request, id, lienholderId):
    """
    Edit Lienholder services on Lien

    Params:
        id: refers to the id of the lien
        *lienholder: the lienholder id, so that we can auto-fill those fields
    """

    if request.POST:
        lien = get_object_or_404(Lien, pk=id)
        lienHolder = get_object_or_404(LienHolder, pk=lienholderId)

        newAnswerDate = request.POST['answer_date']
        newServiceDate = request.POST['service_date']


        if newAnswerDate:
            lienHolder.answer_date = newAnswerDate
        
        if newServiceDate:
            lienHolder.service_date = newServiceDate

        lienHolder.save()

    return HttpResponseRedirect(reverse('lien-view', args = [id,]))