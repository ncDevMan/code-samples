from datetime import datetime
import time as real_time
import json
from funcy import set_in
import pytz
import operator

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render_to_response, get_object_or_404, redirect, render
from django.http import HttpResponseRedirect, HttpResponse, Http404, StreamingHttpResponse
from django.db.models import Q, Count
import requests

from lien.models import Lien, LienOwner
from reporting.utils import get_report_info
from reporting.forms import *
from lien.forms import *

from django.db import connection, transaction
from reporting.calculations.debt_equity import *
from reporting.calculations.paid_unpaid import *
from reporting.reports import *
from files.models import *

from reporting.models import *
from datetime import datetime
import time as real_time
from itertools import chain
from pandas import *
import xlrd

import simplejson
from django.contrib import messages

def get_years():
    years1 = Lien.objects.extra({'year' : "YEAR(date_purchased)"}).values_list('year', flat=True).distinct()
    years1 = list(years1)

    years2 = Lien.objects.extra({'year' : "YEAR(date_paid)"}).values_list('year', flat=True).distinct()
    years2 = list(years2)

    for year in years2:
        if year not in years1 and year is not None:
            years1.append(year)

    years1.sort()
    
    new_list = [year for year in years1 if year != 2010]

    return new_list


@user_passes_test(lambda u: u.is_staff)
def index(request):
    years = get_years()

    current_year = datetime.now().year;

    return render_to_response('reporting/index.html', {'years': years, 'current_year' : current_year})


@user_passes_test(lambda u: u.is_staff)
def yearly_report(request, year):
    # Report Calculations
    units_notes = UnitsNotesReport(year)
    purchased_bills = PurchasedBillReport(year, 'alternate_date_purchased', use_alternate_date_purchased=True)
    bills_paid = BillsPaidReport(year, 'date_paid', use_alternate_date_purchased=True)

    # Monthly Report totals
    total_number_of_units = MonthlyReport.objects.total_units()
    total_number_of_notes = MonthlyReport.objects.total_notes()

    # Current Totals
    try:
        current_totals = CurrentTotal.objects.latest('created_at')
        unpaid_interest_on_notes = current_totals.unpaid_interest_on_notes
        current_cash_on_hand = current_totals.current_cash_on_hand
        total_amount_of_units = current_totals.total_amount_of_units
    except:
        unpaid_interest_on_notes = EMPTY_FIELD
        current_cash_on_hand = EMPTY_FIELD
        total_amount_of_units = Decimal('0.00')

    total_amount_of_notes = MonthlyReport.objects.total_amount_of_notes()

    # Lien Totals and Calculations
    current_potential_interest = Lien.nonwriteoff_objects.potential_interest()

    number_of_bills_held = Lien.nonwriteoff_objects.filter(date_paid__isnull=True).count()
    face_amount_unpaid_bills = Lien.nonwriteoff_objects.face_amount_unpaid_bills()
    average_face_amount_unpaid_bills = face_amount_unpaid_bills / Decimal(str(number_of_bills_held))

    total_assessed_value_on_unpaid = Lien.nonwriteoff_objects.total_assessed_value_on_unpaid()

    total_partnership_equity = total_amount_of_units + total_amount_of_notes

    total_actual_cost_unpaid = Lien.nonwriteoff_objects.total_actual_cost_unpaid();

    context = {
        'year': year,
        'units_notes': units_notes,
        'purchased_bills': purchased_bills,
        'bills_paid': bills_paid,
        'empty_field': EMPTY_FIELD,
        'number_of_bills_held': number_of_bills_held,
        'face_amount_unpaid_bills': face_amount_unpaid_bills,
        'total_assessed_value_on_unpaid': total_assessed_value_on_unpaid,
        'average_face_amount_unpaid_bills': average_face_amount_unpaid_bills,
        'bills_on_payment_plan': Lien.nonwriteoff_objects.on_payment_plan().count(),
        'total_payments_on_payment_plan': Lien.nonwriteoff_objects.total_payments_on_payment_plan(),
        'total_number_of_notes': total_number_of_notes,
        'total_amount_of_notes': total_amount_of_notes,
        'unpaid_interest_on_notes': unpaid_interest_on_notes,
        'total_number_of_units': total_number_of_units,
        'total_amount_of_units': total_amount_of_units,
        'current_potential_interest': current_potential_interest,
        'current_cash_on_hand': current_cash_on_hand,
        'total_partnership_equity': total_partnership_equity,
        'total_actual_cost_unpaid': total_actual_cost_unpaid,
    }

    

    return render_to_response('reporting/year.html', context)


@user_passes_test(lambda u: u.is_staff)
def current_year(request):
    year = datetime.now().year
    return yearly_report(request, year)

@user_passes_test(lambda u: u.is_staff)
def archive(request):
    years = get_years()

    return render_to_response('reporting/archive.html',
                              {'years': years})


@user_passes_test(lambda u: u.is_staff)
def fee_summary_report(request):

    if request.GET.__contains__('skip-cache') and request.GET['skip-cache'] == 'true':
        raw_result = get_report_info(
            'fee_summary_report',
            skip_cache=True
        )
    else:
        raw_result = get_report_info('fee_summary_report')

    fc_result_dict = raw_result['result']
    unix_date_run = raw_result['date_run']
    data_date_run = real_time.strftime(
        '%m/%d/%Y %I:%M %p',
        real_time.localtime(unix_date_run)
    )

    context = set_in(fc_result_dict, ['data_date_run'], data_date_run)
    return render_to_response(
        'reporting/fee_summary_report.html',
        context
    )

@user_passes_test(lambda u: u.is_staff)
def foreclosure_fee_report(request):
    if request.GET.__contains__('skip-cache') and request.GET['skip-cache'] == 'true':
        raw_result = get_report_info(
            'foreclosure_fee_report',
            skip_cache=True
        )
    else:
        raw_result = get_report_info('foreclosure_fee_report')
    fc_result_dict = raw_result['result']
    unix_date_run = raw_result['date_run']
    data_date_run = real_time.strftime(
        '%m/%d/%Y %I:%M %p',
        real_time.localtime(unix_date_run)
    )
    context = set_in(fc_result_dict, ['data_date_run'], data_date_run)
    return render_to_response(
        'reporting/foreclosure_fee_report.html',
        context
    )


@login_required
def tax_lien_pool_report(request):


    if request.GET.__contains__('skip-cache') and request.GET['skip-cache'] == 'true':
        raw_result = get_report_info(
            'tax_lien_pool_report',
            skip_cache=True
        )
    else:
        raw_result = get_report_info('tax_lien_pool_report')

    
    fc_result_dict = raw_result['result']
    unix_date_run = raw_result['date_run']
    data_date_run = real_time.strftime(
        '%m/%d/%Y %I:%M %p',
        real_time.localtime(unix_date_run)
    )
    context = set_in(fc_result_dict, ['data_date_run'], data_date_run)

    return render_to_response('reporting/tax_lien_pool.html', context)


@login_required
def unit_values(request):
    #
    # Debt versus equity
    #
    try:
        current_totals = CurrentTotal.objects.latest('created_at')
        unpaid_interest_on_notes = current_totals.unpaid_interest_on_notes
        total_amount_of_units = current_totals.total_amount_of_units
    except:
        unpaid_interest_on_notes = Decimal('0.00')
        total_amount_of_units = Decimal('0.00')

    total_amount_of_notes = MonthlyReport.objects.total_amount_of_notes()

    total_debt_equity = calc_total(total_amount_of_notes, unpaid_interest_on_notes, total_amount_of_units)
    debt = calc_debt(total_amount_of_notes, unpaid_interest_on_notes, total_debt_equity)
    equity = calc_equity(total_amount_of_units, total_debt_equity)

    #
    # Monthly Unit Values
    #
    # For this section, I create a dictionary of all of the years in the database, along with
    # all the months in each year. First I create the empty dict, then I populate the dict.

    # List of years from MonthlyUnitValues
    years = [y for y in MonthlyUnitValue.objects.exclude(year=2012).values_list('year', flat=True).distinct('year')]
    
    # Remove duplicates by using a set
    year_list = list(set(years))

    # Create dict with format below
    # { 2013: { 1: { 'month_name': 'Jan'}, 2: { 'month_name': 'Feb'}, ... } }
    unit_values_by_year = {}

    # Add months to to dict
    for year in year_list:
        unit_values_by_year[year] = {}
        for m in MONTHS:
            unit_values_by_year[year][m[0]] = {
                'month_name': m[1],
                'unit_value': None
            }

    # Populate dict from database
    unit_values = MonthlyUnitValue.objects.exclude(year=2012)
    for unit_value in unit_values:
        unit_values_by_year[int(unit_value.year)][unit_value.month]['unit_value'] = unit_value

    #
    # Debt Stats
    #
    current_debt_stats = CurrentDebtStat.objects.latest('created_at')
    average_rate = current_debt_stats.average_rate
    highest_rate = current_debt_stats.highest_rate
    lowest_rate = current_debt_stats.lowest_rate
    average_position = current_debt_stats.average_position
    highest_position = current_debt_stats.highest_position
    lowest_position = current_debt_stats.lowest_position
    asset_position_due = current_debt_stats.asset_position_due
    amount_date = current_debt_stats.amount_date


    #
    # Context
    #
    context = {
        # Debt equity
        'unpaid_interest_on_notes': unpaid_interest_on_notes,
        'total_amount_of_units': total_amount_of_units,
        'total_amount_of_notes': total_amount_of_notes,
        'total_debt_equity': total_debt_equity,
        'debt': debt,
        'equity': equity,

        # Graphing Unit Values
        'months': MonthlyUnitValue.objects.all(),
        'unit_values_by_year': unit_values_by_year,

        # Debt stats
        'average_rate': average_rate,
        'highest_rate': highest_rate,
        'lowest_rate': lowest_rate,
        'average_position': average_position,
        'highest_position': highest_position,
        'lowest_position': lowest_position,
        'asset_position_due': asset_position_due,
        'amount_date': amount_date,

        # Misc
        'now': datetime.now()
    }

    return render_to_response('reporting/unit_values.html', context)





@login_required
def test(request):
	paid = PaidLienCalculation()
	unpaid = UnpaidLienCalculation()
	return render_to_response('reporting/test.html',
							  {'paid': paid, 'unpaid': unpaid})

@login_required
def lien_status_report(request):  
    
    form = SearchForm()
    date_form = DateSearchForm()  

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
    context = set_in(fc_result_dict, ['data_date_run'], data_date_run)
    context['form'] = form
    context['date_form'] = date_form
    
    return render_to_response('reporting/lien_status_report.html', context)

@login_required
def bad_lien_report(request):  

    if request.GET.__contains__('skip-cache') and request.GET['skip-cache'] == 'true':
        raw_result = get_report_info(
            'bad_lien_report',
            skip_cache=True
        )
    else:
        raw_result = get_report_info('bad_lien_report')
    fc_result_dict = raw_result['result']
    unix_date_run = raw_result['date_run']
    data_date_run = real_time.strftime(
        '%m/%d/%Y %I:%M %p',
        real_time.localtime(unix_date_run)
    )
    context = set_in(fc_result_dict, ['data_date_run'], data_date_run)
    
    return render_to_response('reporting/bad_liens.html', context)

@login_required
def call_list_by_county(request):
    counties = [
        # operator.attrgetter('name', 'id')(county)
        getattr(county, 'name')
        for county in County.objects.all()
    ]

    # Removing that annoying blank one
    counties = filter(None, counties);

    context = {"counties": counties}

    return render(request, 'reporting/call_list_by_county.html', context)

@login_required
def inspection_report_by_county(request):
    counties = [
        getattr(county, 'name')
        for county in County.objects.all()
    ]
    context = {"counties": counties}
    return render(request, 'reporting/inspection_report_by_county.html', context)


@login_required
def subsequent_lien_litigation_report(request):
    lien_list = Lien.objects.filter(Q(status=76) & Q(date_first_letter__isnull=True))

    lien_list_ids = []

    for l in lien_list:
        lien_list_ids.append(int(l.id))

    lien_count = len(lien_list_ids)

    context = {
        'lien_list': lien_list,
        'lien_list_ids': lien_list_ids,
        'lien_count': lien_count
    }

    return render_to_response('reporting/subsequent_lien_litigation_report.html', context)




@login_required
def call_list_report(request):
    
    county = request.GET.get('counties', None)

    if(county == 'All'):
        call_list = Lien.objects.filter(Q(status=74)).order_by('tax_year')
    else:
        call_list = Lien.objects.filter(Q(status=74),  Q(county__name=county)).order_by('tax_year')

    days_list = []

    for lien in call_list:
        if lien.get_last_note != 'No Note': 
            days_list.append(lien.get_last_note)

    average = sum(days_list) / len(days_list)
    max_day = max(days_list)
    min_day = min(days_list)

    call_list_property_ids = []
    call_list_ids = []
    call_list_unique_property_ids = []

    for lien in call_list:
        call_list_ids.append(int(lien.id))
        if lien.property_id in call_list_property_ids:
            pass
        else:
            call_list_property_ids.append(lien.property_id)
            call_list_unique_property_ids.append(int(lien.id)) 

    call_list_ids_count = len(call_list_ids)
    call_list_unique_property_ids_count = len(call_list_unique_property_ids) 
    

    context = {
        'county': county,
        'average': average,
        'max_day': max_day,
        'min_day': min_day,
        'call_list_ids': call_list_ids,
        'call_list_unique_property_ids': call_list_unique_property_ids,
        'call_list_ids_count': call_list_ids_count,
        'call_list_unique_property_ids_count': call_list_unique_property_ids_count,
    }

    return render_to_response('reporting/call_list.html', context)


@login_required
def subsequent_lien_litigation_report(request):
    lien_list = Lien.objects.filter(Q(status=76) & Q(date_first_letter__isnull=True))

    lien_list_ids = []

    for l in lien_list:
        lien_list_ids.append(int(l.id))

    lien_count = len(lien_list_ids)

    context = {
        'lien_list': lien_list,
        'lien_list_ids': lien_list_ids,
        'lien_count': lien_count
    }

    return render_to_response('reporting/subsequent_lien_litigation_report.html', context)

@login_required
def inspection_report(request):
    county = request.GET.get('counties', None)
    status = request.GET.get('status', None);
    
    status_label = '';

    if status == 'pre-lit':
        inspection_list = Lien.objects.filter(Q(county__name=county) & (Q(status=74))).order_by('tax_year')
        status_label = 'Pre-Lit'
    elif status == 'suit-filed':
        inspection_list = Lien.objects.filter(Q(county__name=county) & (Q(status=76))).order_by('tax_year')
        status_label = 'Suit Filed'
    else:
        inspection_list = Lien.objects.filter(Q(county__name=county) & (Q(status=74) | Q(status=76))).order_by('tax_year')
        status_label = 'Pre-Lit or Suit Filed'
    

    inspection_report_ids = []
    inspection_report_property_ids = []
    inspection_report_unique_property_ids = []


    for lien in inspection_list:
        inspection_report_ids.append(int(lien.id))
        if lien.property_id not in inspection_report_property_ids:
            inspection_report_property_ids.append(lien.property_id)
            inspection_report_unique_property_ids.append(int(lien.id))
    
    inspection_report_bill_count = len(inspection_report_ids)
    inspection_report_property_count = len(inspection_report_unique_property_ids)

    context = {
        'county': county,
        'inspection_list': inspection_list,
        'inspection_report_unique_property_ids': inspection_report_unique_property_ids,
        'inspection_report_bill_count': inspection_report_bill_count,
        'inspection_report_property_count': inspection_report_property_count,
	'status_label': status_label
    }

    return render_to_response('reporting/inspection_report.html', context)




@login_required
def pool_purchase_search(request):

    if request.method == 'GET':
        form = PoolPurchaseActivityForm(request.GET)

        if form.is_valid():

            if form.cleaned_data['purchased_from_options']:
                if form.cleaned_data['before_date'] and form.cleaned_data['after_date']:
                    # Remove writeoff from closed
                    closed = Lien.objects.filter(purchased_from_new_id=form.cleaned_data['purchased_from_options']).filter(date_paid__range=(form.cleaned_data['before_date'], form.cleaned_data['after_date'] )).exclude(second_status_id = 42)
                    write_off = Lien.objects.filter(purchased_from_new_id=form.cleaned_data['purchased_from_options']).filter(date_paid__range=(form.cleaned_data['before_date'], form.cleaned_data['after_date'])).filter(second_status_id = 42)


                    remaining = Lien.objects.filter(purchased_from_new_id=form.cleaned_data['purchased_from_options']).filter(date_paid__isnull=True)
                    total = Lien.objects.filter(purchased_from_new_id=form.cleaned_data['purchased_from_options'])

                    remaining_total_interest = 0
                    remaining_count = 0

                    for lien in remaining:
                        remaining_count += 1
                        remaining_total_interest += lien.total_interest

                    closed_collected_interest = 0
		    collected_total_face_amount = 0
                    closed_count = 0

                    for lien in closed:
                        closed_count += 1
                        closed_collected_interest += lien.total_interest_breakdown
			collected_total_face_amount += lien.total_lien_amount_breakdown

                    # collected_total_face_amount = closed.aggregate(face_amount_closed=Sum('lien_amount'))['face_amount_closed']
                    
		    if collected_total_face_amount is None:
                        collected_total_face_amount = 0

		    closed_total_collected = collected_total_face_amount + closed_collected_interest


                    write_off = {
                        'write_off': write_off,
                        'number_of_liens': write_off.count(),
                        'face_amount': write_off.aggregate(face_amount_closed=Sum('lien_amount')),
                        'actual_cost': write_off.aggregate(actual_cost_closed=Sum('actual_cost'))
                    }

                    closed_liens = {
                        'closed': closed,
                        'number_of_liens': closed.count(),
                        'face_amount': closed.aggregate(face_amount_closed=Sum('lien_amount')),
                        'actual_cost': closed.aggregate(actual_cost_closed=Sum('actual_cost')), 
                        'closed_collected_interest': closed_collected_interest,
                        'closed_count': closed_count,
                        'closed_total_collected': closed_total_collected,
			'collected_total_face_amount': collected_total_face_amount
                    }

                    potential_collections_face_amount = remaining.aggregate(face_amount_remaining=Sum('lien_amount'))['face_amount_remaining']
                    
		    if potential_collections_face_amount is None:
                        potential_collections_face_amount = 0

		    potential_collections = potential_collections_face_amount + remaining_total_interest

                    remaining_liens = {
                        'remaining': remaining,
                        'remaining_number_of_liens': remaining.count(),
                        'face_amount': remaining.aggregate(face_amount_remaining=Sum('lien_amount')),
                        'actual_cost': remaining.aggregate(actual_cost_remaining=Sum('actual_cost')),
                        'remaining_count': remaining_count, 
                        'remaining_total_interest': remaining_total_interest,
                        'potential_collections': potential_collections
                    }

                    total_liens = {
                        'total_number_of_liens': total.count(),
                        'face_amount': total.aggregate(face_amount_total=Sum('lien_amount')),
                        'actual_cost': total.aggregate(actual_cost_total=Sum('actual_cost')),
                    }

                    purchased_from_name = PurchasedFromNew.objects.get(id=form.cleaned_data['purchased_from_options']);

                    search_params = {
                        'purchased_from': purchased_from_name.name,
                        'before_date': form.cleaned_data['before_date'],
                        'after_date': form.cleaned_data['after_date']
                    }

                    context = {
                        'closed_liens': closed_liens,
                        'write_off_liens' : write_off,
                        'remaining_liens': remaining_liens,
                        'total_liens': total_liens,
                        'form': form,
                        'search_params': search_params,
                    }

            return render_to_response('reporting/pool_purchase_reporting.html', context)
        else:    
            return HttpResponseRedirect(reverse('reporting_pool_purchase_activity'))
    else:
        return HttpResponseRedirect(reverse('reporting_pool_purchase_activity'))


@login_required
def pool_purchase_activity(request):

    form = PoolPurchaseActivityForm()

    return render_to_response('reporting/pool_purchase_activity.html', { 'form': form })

@user_passes_test(lambda u: u.is_staff)
def inspections_report(request):
    return render_to_response(
        'reporting/inspections_report.html',
        {}
    )




def getSaleLiens(before, after):
    lienList = [];
    total = 0;

    liens = Expense.objects.filter(
        note__contains='Sale Attendance'
    )

    for l in liens:
        lien = Lien.objects.get(id = int(l.lien_id));
        
        if lien.date_paid is not None:
            if before <= lien.date_paid <= after:
                total += l.amount;
                lienList.append(int(l.lien_id));

    return lienList, total;


def getInspectionLiens(before, after):
    lienList = [];
    total = 0;


    liens = Expense.objects.filter(
        note__contains='Inspection of property'
    )

    for l in liens:
        lien = Lien.objects.get(id = int(l.lien_id));
        
        if lien.date_paid is not None:
            if before <= lien.date_paid <= after:
                total += l.amount;
                lienList.append(int(l.lien_id));
    return (lienList, total);


@user_passes_test(lambda u: u.is_staff)
def sale_attendance(request):
    form = SaleInspectionForm();

    if request.method == 'GET':
        form = SaleInspectionForm(request.GET);


    if form.is_valid():
        before = form.cleaned_data['before_date'];
        after = form.cleaned_data['after_date'];

    

        inspectionLiens, inspectionTotal = getInspectionLiens(before, after);
        saleLiens, saleTotal = getSaleLiens(before, after);

        context = {
            'inspection_ids': inspectionLiens,
            'sale_ids': saleLiens,
            'lien_count': len(saleLiens) + len(inspectionLiens) - 2,
            'inspectionTotal': inspectionTotal,
            'saleTotal': saleTotal,
            'form': form,
            'before': before,
            'after': after,
            'page_title': 'Inspection and Sale Attendance',
            'page_subtitle': 'Bills that have inspection fee and are paid',
            'editable_fields': '[]'
        }

        return render_to_response(
                'reporting/bypass/inspection_report.html',
                context
        )
    else:
        return render_to_response(
            'lien/index.html',
            {}
        )


@user_passes_test(lambda u: u.is_staff)
def generic_lien_list(request):
    def get_editable_field_type(field):
        '''
        For editable fields, we need to know what type the field on the
        model is. Else we cannot validate that users aren't typing in
        strings for date. This returns either `String`, `Date`,
        or `Integer`.
        '''
        django_type = type(Lien._meta.get_field(field))
        if 'DateField' in str(django_type):
            return 'Date'
        elif 'TimeField' in str(django_type):
            return 'Time'
	elif 'CharField' in str(django_type):
            return 'String'
        elif 'IntegerField' in str(django_type):
            return 'Integer'
        elif 'DecimalField' in str(django_type):
            return 'Decimal'
        elif 'BooleanField' in str(django_type):
            return 'Boolean'
        else:
            raise ValueError(
                "type %s is not supported yet" % django_type
            )

    if request.POST:
        post_dict = request.POST.dict()
        lien_ids = json.loads(post_dict[u'lien-ids'])

        if ('filter' in post_dict):
            filter_sort = json.loads(post_dict[u'filter'])
        else:
            filter_sort = {"field": "id", "reverse": False}

        other_fields = post_dict.get(u'other-fields', [])
        filter_fields = post_dict.get(u'filter-fields', [])
        display_fields = post_dict[u'display-fields']
        editable_fields_raw = post_dict.get(u'editable-fields', '[]')
        editable_fields = json.loads(editable_fields_raw)
        field_names_and_types = [
            (lambda n: {'field-name': n, 'type': get_editable_field_type(n)})(n)
            for n in editable_fields
        ]
        page_title = post_dict[u'page-title']
        page_subtitle = post_dict[u'page-subtitle']

        
        context = {
            'lien_ids': lien_ids,
            'display_fields': display_fields,
            'filter_fields': filter_fields,
            'page_title': page_title,
            'page_subtitle': page_subtitle,
            'other_fields': other_fields,
            'filter_sort': json.dumps(filter_sort),
            'editable_fields': json.dumps(field_names_and_types)
        }
        return render_to_response(
            'reporting/generic_list_view.html',
            context
        )
    else:
        return render_to_response(
            'reporting/generic_liens_select.html',
            {}
        )


@user_passes_test(lambda u: u.is_staff)
def changelog(request):

    return render_to_response('reporting/changelog.html')




@login_required
def order_title_search_report(request):

    form = OrderTitleSearchForm()

    if request.method == 'GET':
        form = OrderTitleSearchForm(request.GET)

    if form.is_valid():
        status = form.cleaned_data['status']
        county = form.cleaned_data['county']

    liens = Lien.objects.filter(order_title=True)
    totalCount = liens.count()

    filteredByStatusAndCountyCount = 'N/A'
    filteredByStatusCount = 'N/A'
    filteredByCountyCount = 'N/A'
    lienIds = []
    propertyIds = []

    if status and county:
        filteredByStatusAndCounty = liens.filter(county=county, status=status).order_by('tax_year')
        totalCount = filteredByStatusAndCounty.count()
        for l in filteredByStatusAndCounty:

            if l.property_id in propertyIds:
                pass
            else:
                lienIds.append(int(l.id))
                propertyIds.append(l.property_id)
    elif status:
        filteredByStatus = liens.filter(status=status).order_by('tax_year')
        totalCount = filteredByStatus.count()
        for l in filteredByStatus:
            if l.property_id in propertyIds:
                pass
            else:
                lienIds.append(int(l.id))
                propertyIds.append(l.property_id)
    elif county:
        filteredByCounty = liens.filter(county=county).order_by('tax_year')
        totalCount = filteredByCounty.count()
        for l in filteredByCounty:
            if l.property_id in propertyIds:
                pass
            else:
                lienIds.append(int(l.id))
                propertyIds.append(l.property_id)
    else:
        for l in liens.order_by('tax_year'):
            if l.property_id in propertyIds:
                pass
            else:
                lienIds.append(int(l.id))
                propertyIds.append(l.property_id)

    uniqueCount = len(propertyIds)

    return render_to_response('reporting/order_title_report.html',
        {
            'totalCount' : totalCount,
            'form': form,
            'status': status,
            'filteredByStatusAndCountyCount': filteredByStatusAndCountyCount,
            'filteredByStatusCount': filteredByStatusCount,
            'filteredByCountyCount': filteredByCountyCount,
            'county': county,
            'lienIds': lienIds,
            'uniqueCount': uniqueCount
        }
    )



@login_required
def additional_purchases_report(request):

    # Get liens where bubble is clicked
    liens = Lien.objects.filter(purchase_additional=True)

    # This will help us get the earliest tax year for the report
    liens = liens.order_by('tax_year')
    totalCount = liens.count()

    lienIds = []
    propertyIds = []

    for l in liens:
        # Dont forget to check for dupes!!!
        if l.property_id in propertyIds:
            pass
        else:
            lienIds.append(int(l.id))
            propertyIds.append(l.property_id)

    return render_to_response('reporting/additional_purchases_report.html',
        {
           
            'lienIds': lienIds,
	    'propertyCount': len(propertyIds), 
        }
    )



@user_passes_test(lambda u: u.is_staff)
def progress_report(request):
    form = ProgressReportSearchForm()

    lienIds = []
    newLienIds = []
    propertyIds = []
    totalTransactions = (0,)

    i = 1
    if request.method == 'GET':
        form = ProgressReportSearchForm(request.GET)

    if form.is_valid():
        before = form.cleaned_data['end_date']
        after = form.cleaned_data['start_date']
        county = form.cleaned_data['county']
        attorney = form.cleaned_data['attorney']
    else: 
        print('form is not valid')

    if before and after:
        cursor = connection.cursor()
        try:
            if county and attorney:
                # distinct with property_id
                query = 'SELECT DISTINCT id, CONCAT(b.county_id,"---",b.map_number) as property_id from (Select lien_id from lien_expense where (expense_date between date(%s) and date(%s)) and (expense_class_id=14 || expense_class_id=15) UNION ALL Select lien_id from lien_note Where CAST(created_at as DATE) between date(%s) and date(%s) UNION ALL select lien_id from files_uploadedfile where CAST(created_at as DATE) between date(%s) and date(%s)) as a inner join lien_lien b ON id=lien_id AND (attorney_id=%s and county_id=%s)' 
                # get all transactions
                query_transactions = 'SELECT COUNT(*) as count from (Select lien_id from lien_expense where (expense_date between date(%s) and date(%s)) and (expense_class_id=14 || expense_class_id=15) UNION ALL Select lien_id from lien_note Where CAST(created_at as DATE) between date(%s) and date(%s) UNION ALL select lien_id from files_uploadedfile where CAST(created_at as DATE) between date(%s) and date(%s)) as a inner join lien_lien b ON id=lien_id AND (attorney_id=%s and county_id=%s)'
                args = [after,before,after,before,after,before,attorney.id,county.id]
            elif county is None and attorney:
                query =  'SELECT DISTINCT id, CONCAT(b.county_id,"---",b.map_number) as property_id from (Select lien_id from lien_expense where (expense_date between date(%s) and date(%s)) and (expense_class_id=14 || expense_class_id=15) UNION ALL Select lien_id from lien_note Where CAST(created_at as DATE) between date(%s) and date(%s) UNION ALL select lien_id from files_uploadedfile where CAST(created_at as DATE) between date(%s) and date(%s)) as a inner join lien_lien b ON id=lien_id AND attorney_id=%s'
                query_transactions = 'SELECT COUNT(*) as count from (Select lien_id from lien_expense where (expense_date between date(%s) and date(%s)) and (expense_class_id=14 || expense_class_id=15) UNION ALL Select lien_id from lien_note Where CAST(created_at as DATE) between date(%s) and date(%s) UNION ALL select lien_id from files_uploadedfile where CAST(created_at as DATE) between date(%s) and date(%s)) as a inner join lien_lien b ON id=lien_id AND attorney_id=%s'
                args = [after,before,after,before,after,before,attorney.id]
                
            elif county and (not attorney):
                query = 'SELECT DISTINCT id, CONCAT(b.county_id,"---",b.map_number) as property_id from (Select lien_id from lien_expense where (expense_date between date(%s) and date(%s)) and (expense_class_id=14 || expense_class_id=15) UNION ALL Select lien_id from lien_note Where CAST(created_at as DATE) between date(%s) and date(%s) UNION ALL select lien_id from files_uploadedfile where CAST(created_at as DATE) between date(%s) and date(%s)) as a inner join lien_lien b ON id=lien_id AND county_id=%s)'
                query_transactions = 'SELECT COUNT(*) as count from (Select lien_id from lien_expense where (expense_date between date(%s) and date(%s)) and (expense_class_id=14 || expense_class_id=15) UNION ALL Select lien_id from lien_note Where CAST(created_at as DATE) between date(%s) and date(%s) UNION ALL select lien_id from files_uploadedfile where CAST(created_at as DATE) between date(%s) and date(%s)) as a inner join lien_lien b ON id=lien_id AND county_id=%s)'
                args = [after,before,after,before,after,before,county.id]   
            elif county is None and (not attorney):
                query = 'SELECT DISTINCT id, CONCAT(b.county_id,"---",b.map_number) as property_id from (Select lien_id from lien_expense where (expense_date between date(%s) and date(%s)) and (expense_class_id=14 || expense_class_id=15) UNION ALL Select lien_id from lien_note Where CAST(created_at as DATE) between date(%s) and date(%s) UNION ALL select lien_id from files_uploadedfile where CAST(created_at as DATE) between date(%s) and date(%s)) as a inner join lien_lien b ON id=lien_id'
                query_transactions = 'SELECT COUNT(*) as count from (Select lien_id from lien_expense where (expense_date between date(%s) and date(%s)) and (expense_class_id=14 || expense_class_id=15) UNION ALL Select lien_id from lien_note Where CAST(created_at as DATE) between date(%s) and date(%s) UNION ALL select lien_id from files_uploadedfile where CAST(created_at as DATE) between date(%s) and date(%s)) as a inner join lien_lien b ON id=lien_id'
                args = [after,before,after,before,after,before]
            else:
                print "here"

            cursor.execute(query,args)
            results = cursor.fetchall()
            
            cursor.execute(query_transactions,args)
            totalTransactions = cursor.fetchone()

            # tuple (id, property_id)
            for r in results:
                newLienIds.append(int(r[0]))
                propertyIds.append(r[1])

        finally:
            cursor.close()
    
    return render_to_response('reporting/progress_report.html',
        {   
            'form': form,
            'before': before,
            'after': after,
            'lienIds': newLienIds,
            'transactions' : totalTransactions[0],
            'totalCount' : len(newLienIds)
        }
    )

@user_passes_test(lambda u: u.is_staff)
def action_date_search_report(request):

    form = ActionDateSearchForm()
    
    if request.method == 'GET':
        form = ActionDateSearchForm(request.GET)

    before = ''
    after = ''
    county = ''

    if form.is_valid():
        before = form.cleaned_data['start_date']
        after = form.cleaned_data['end_date']
        county = form.cleaned_data['county']
    else: 
        print('form is not valid')

    liens = Lien.objects.filter(action_date__isnull=False)
    totalCount = liens.count()

    filteredByDateAndCountyCount = 'N/A'
    filteredByDateCount = 'N/A'
    filteredByCountyCount = 'N/A'
    lienIds = []

    if before and after and county:
        filteredByDateAndCounty = liens.filter(county=county, action_date__range=(before,after))
        filteredByDateAndCountyCount = filteredByDateAndCounty.count()
        for l in filteredByDateAndCounty:
            lienIds.append(int(l.id))
    elif before and after:
        filteredByDate = liens.filter(action_date__range=(before, after))
        filteredByDateCount = filteredByDate.count()
        for l in filteredByDate:
            lienIds.append(int(l.id))
    elif county:
        filteredByCounty = liens.filter(county=county)
        filteredByCountyCount = filteredByCounty.count()
        for l in filteredByCounty:
            lienIds.append(int(l.id))
    # else:
    #     for l in liens:
    #         lienIds.append(int(l.id))

    return render_to_response('reporting/action_date_search_report.html', 
        {
            'totalCount' : totalCount,
            'form': form,
            'before': before,
            'after': after,
            'filteredByDateAndCountyCount': filteredByDateAndCountyCount,
            'filteredByDateCount': filteredByDateCount,
            'filteredByCountyCount': filteredByCountyCount,
            'county': county,
            'lienIds': lienIds,
        }
    )



@user_passes_test(lambda u: u.is_staff)
def special_asset_search_report(request):

    form = SpecialAssetSearchForm()

    if request.method == 'GET':
        form = SpecialAssetSearchForm(request.GET)

    if form.is_valid():
        status = form.cleaned_data['status']
        county = form.cleaned_data['county']
    else: 
        print('form is not valid')

    liens = Lien.objects.filter(special_asset=True)
    totalCount = liens.count()

    filteredByStatusAndCountyCount = 'N/A'
    filteredByStatusCount = 'N/A'
    filteredByCountyCount = 'N/A'
    lienIds = []

    if status and county:
        filteredByStatusAndCounty = liens.filter(county=county, status=status)
        filteredByStatusAndCountyCount = filteredByStatusAndCounty.count()
        for l in filteredByStatusAndCounty:
            lienIds.append(int(l.id))
    elif status:
        filteredByStatus = liens.filter(status=status)
        filteredByStatusCount = filteredByStatus.count()
        for l in filteredByStatus:
            lienIds.append(int(l.id))
    elif county:
        filteredByCounty = liens.filter(county=county)
        filteredByCountyCount = filteredByCounty.count()
        for l in filteredByCounty:
            lienIds.append(int(l.id))
    else:
        for l in liens:
            lienIds.append(int(l.id))

    return render_to_response('reporting/special_asset_report.html', 
        {
            'totalCount' : totalCount,
            'form': form,
            'status': status,
            'filteredByStatusAndCountyCount': filteredByStatusAndCountyCount,
            'filteredByStatusCount': filteredByStatusCount,
            'filteredByCountyCount': filteredByCountyCount,
            'county': county,
            'lienIds': lienIds,
        }
    )


@user_passes_test(lambda u: u.is_staff)
def purchased_property_search_report(request):

    form = PurchasedPropertySearchForm()

    if request.method == 'GET':
        form = PurchasedPropertySearchForm(request.GET)

    if form.is_valid():
        status = form.cleaned_data['status']
        county = form.cleaned_data['county']
    else: 
        print('form is not valid')

    liens = Lien.objects.filter(property_purchased=True)
    totalCount = liens.count()

    filteredByStatusAndCountyCount = 'N/A'
    filteredByStatusCount = 'N/A'
    filteredByCountyCount = 'N/A'
    lienIds = []
    propertyIds = []

    if status and county:
        filteredByStatusAndCounty = liens.filter(county=county, status=status).order_by('tax_year')
        filteredByStatusAndCountyCount = filteredByStatusAndCounty.count()
        for l in filteredByStatusAndCounty:

            if l.property_id in propertyIds:
                pass
            else:
                lienIds.append(int(l.id))
                propertyIds.append(l.property_id)
    elif status:
        filteredByStatus = liens.filter(status=status).order_by('tax_year')
        filteredByStatusCount = filteredByStatus.count()
        for l in filteredByStatus:
            if l.property_id in propertyIds:
                pass
            else:
                lienIds.append(int(l.id))
                propertyIds.append(l.property_id)
    elif county:
        filteredByCounty = liens.filter(county=county).order_by('tax_year')
        filteredByCountyCount = filteredByCounty.count()
        for l in filteredByCounty:
            if l.property_id in propertyIds:
                pass
            else:
                lienIds.append(int(l.id))
                propertyIds.append(l.property_id)
    else:
        for l in liens.order_by('tax_year'):
            if l.property_id in propertyIds:
                pass
            else:
                lienIds.append(int(l.id))
                propertyIds.append(l.property_id)

    uniqueCount = len(propertyIds)

    return render_to_response('reporting/purchased_property_report.html', 
        {
            'totalCount' : totalCount,
            'form': form,
            'status': status,
            'filteredByStatusAndCountyCount': filteredByStatusAndCountyCount,
            'filteredByStatusCount': filteredByStatusCount,
            'filteredByCountyCount': filteredByCountyCount,
            'county': county,
            'lienIds': lienIds
        }
    )

@user_passes_test(lambda u: u.is_staff)
def pre_lit_expenses(request):
    lienIds = []
    propertyIds = []

    form = CountySearchForm()

    if request.method == 'GET':
        form = CountySearchForm(request.GET)

    if form.is_valid():
        county = form.cleaned_data['county']
    else: 
        print('form is not valid')
    
    liens = Lien.objects.filter(date_paid__isnull=True)

    if county:
        
        filteredByStatusAndCounty = liens.filter(status__id=74, county = county)
        for l in filteredByStatusAndCounty:
            expenses = Expense.objects.filter(lien_id = l.id)

            if expenses:
                lienIds.append(int(l.id))
    else:
        filteredByStatusAndCounty = liens.filter(status__id=74)
        filteredByStatusAndCountyCount = filteredByStatusAndCounty.count()
        for l in filteredByStatusAndCounty:
            expenses = Expense.objects.filter(lien_id = l.id)
            expenses = expenses.exclude(expense_class_id = 17)

            if expenses:
                lienIds.append(int(l.id))

    return render_to_response('reporting/pre_lit_expenses.html', 
    
        {
            'lienIds': lienIds,
            'form': form,
            'county': county,
            'filteredByStatusAndCountyCount': len(lienIds)
        }
    )




@user_passes_test(lambda u: u.is_staff)
def fox_payable(request):
    from lien.shortcuts import render_or_export, export_to_csv, stream_csv

    lienIds = []
    liens = False

    form = DateRangeAndLienOwnerForm()

    if request.method == 'GET':
        form = DateRangeAndLienOwnerForm(request.GET)
        

    if form.is_valid():
        start = form.cleaned_data['start_date']
        end = form.cleaned_data['end_date']
        lien_owner = form.cleaned_data['lien_owner']
    else: 
        print('form is not valid')

    

    if start and end:
        liens = Lien.objects.filter(date_paid__range=[start, end])

    if lien_owner and liens:
        # if there is a start and end AND lienowner, we will go here
        liens = liens.filter(lien_owner = lien_owner)
    elif lien_owner and not liens:
        # If no start or end exists, we will query by lien owner only and make sure the date is paid
        liens = Lien.objects.filter(lien_owner = lien_owner, date_paid__isnull = False)

    if liens:
        for l in liens:
            lienIds.append(int(l.id))

    if liens:
        
	EXPORT_FIELDS = [
            'lien_owner',
            'id',
            'status',
            'second_status',
            'date_paid',
            'county',
            'bill_number',
            'tax_year',
            'purchased_from_new',
            'date_purchased',
            'alternate_date_purchased',
            'total_payment_plan_fee_breakdown',
            'total_litigation_costs_breakdown',
            'total_lien_amount_breakdown',
            'total_interest_breakdown',
            'total_attorney_fee_breakdown',
            'total_litigation_expenses_breakdown',
            'total_admin_fee_breakdown',
        ]
	response = StreamingHttpResponse(
            stream_csv(liens, fields=EXPORT_FIELDS, related_fields=[], short_export=False, with_notes=False),
            content_type="text/csv"
        )
        response['Content-Disposition'] = 'attachment; filename=date_paid_filter.csv'
        return response
    else:
        return render_to_response('reporting/fox_payable.html', 
            {
                'totalCount' : len(lienIds),
                'form': form,
                'start_date': start,
                'end_date': end,
                'lien_owner': lien_owner,
                'lien_ids': lienIds
            }
        )

@user_passes_test(lambda u: u.is_staff)
def notification_report(request):
    """A function to connect with notifications frontend application"""


    
    form = NotificationReportForm();

    if request.method == 'POST':
        formEntered = True
        form = NotificationReportForm(request.POST)
    else:
        formEntered = False


    

    before = None
    after = None
    county = None
    creator = None
    status = None
    if form.is_valid():
        before = form.cleaned_data['start_date']
        after = form.cleaned_data['end_date']
        county = form.cleaned_data['county']
        creator = form.cleaned_data['creator']
        status = form.cleaned_data['status'] 


    return render_to_response('reporting/notifications_report.html',
        {
            "form": form,
            "before": str(before) if before else None,
            "after": str(after) if after else None,
            "county": county,
            "creator": creator,
	        "status": status,
            "formEntered": formEntered
        }
    )


