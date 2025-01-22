# Create your views here.
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.utils import simplejson
from django.shortcuts import get_object_or_404

# float formatting for compositor.
from lien.templatetags.money import make_money

from datetime import datetime
from dateutil import parser
from cerberus import Validator
from decimal import Decimal
import json
import simplejson

from lien.templatetags.money import make_money

from lien.models import Expense, ExpenseClass, Lien, County

from reporting.forms import *
from reporting.calculations.debt_equity import *
from reporting.calculations.paid_unpaid import *
from reporting.reports import *
from reporting.models import *

from api.core import *

from utilities.letters import letterToProp, markLetterListSent, addAutomatedNote, createLabels

from django.contrib.auth.models import User

passcode = '0bfe985e-5961-11e8-8f2d-0242ac110003'

import api.core as core

import activity.views as activity

from django.db.models import Q




def get_third_status_liens(request):
    json_response = simplejson.dumps({
            'success': True,
            'calculations': [{}]
        });

    return HttpResponse(json_response, mimetype="application/json")


def get_composite_calculations(request):
    '''
    This will get the composite calculations for the whole lien list AND the associated liens. 

    '''

    if request.method == 'POST':
        post_dict = json.loads(request.body)
        lien_list = post_dict['lien_ids']
    else:
        lien_list = []



    face_amount = core.get_face_amount(lien_list, True)
    interest_amount = core.get_interest_amount(lien_list, True)
    foreclosure_costs_amount = core.get_foreclosure_costs_amount(lien_list, True)
    foreclosure_billing_amount = core.get_foreclosure_attorney_amount(lien_list, True)
    other_costs_amount = core.get_other_costs_amount(lien_list, True)
    admin_amount = core.get_admin_amount(lien_list, True)
    pre_lit_amount = core.get_pre_lit_amount(lien_list, True)
    lit_amount = core.get_lit_amount(lien_list, True)

    calculations = [
        {'calc_field': 'face_amount', 'value': make_money(face_amount)},
        {'calc_field': 'interest_amount', 'value': make_money(interest_amount)},
        {'calc_field': 'foreclosure_costs_amount', 'value': make_money(foreclosure_costs_amount)},
        {'calc_field': 'foreclosure_billing_amount', 'value': make_money(foreclosure_billing_amount)},
        {'calc_field': 'other_costs_amount', 'value': make_money(other_costs_amount)},
        {'calc_field': 'admin_amount', 'value': make_money(admin_amount)},
        {'calc_field': 'pre_lit_amount', 'value': make_money(pre_lit_amount)},
        {'calc_field': 'lit_amount', 'value': make_money(lit_amount)},
    ]

    json_response = simplejson.dumps({
            'success': True,
            'calculations': calculations
        });

    return HttpResponse(json_response, mimetype="application/json") 



def notification_report_tasks(request):
    '''
    Loads initial task data to notification manager app.

    If this request method is a post, then the user is updating task data from
    the notification manager app.
    '''
    from collections import OrderedDict
    
    # admin can see all task entries by all users.
    user = request.user
    is_admin = check_is_admin(user.id)

    # this post updates single task and sends back response with updated info.
    if request.method == 'POST':
        post_dict = json.loads(request.body)
        task = NotificationReport.objects.filter(pk=post_dict['item']['id'])
        task.update(status=post_dict['status'])
        
        # maintain the order and return the updated status with the data.
        updateValue = task.values_list('status')[0]
        objFields = ['id','Index','Creator','Lien','Recipients','Created','Description', 'Goal Date', 'Status']
        
        taskObject = list()
        for field in objFields:
            if(field == 'Status'):
                taskObject.append((field,updateValue[0]))
            else:
                taskObject.append((field,post_dict['item'][field]))
        
        updatedTask = OrderedDict(taskObject)
        
        json_response = simplejson.dumps({
            'success': True,
            'task': updatedTask
        });

        return HttpResponse(json_response, mimetype="application/json") 
    
    # options for task status
    status_types = [
        {'value': 'completed', 'label': 'Completed'},
        {'value': 'request_review', 'label': 'Request For Review'},
        {'value': 'not_complete', 'label': 'Not Complete'}
    ]

    # verify if adim is logged in.
    if not is_admin['verified']:
        tasks = user.notificationreport_set.all()
    else:
        tasks = NotificationReport.objects.all()

    task_list = [];
    count = 0
    
    # building initial task data on request.
    for task in tasks:
        recipients = task.notification_group.all()
        
        taskObject = OrderedDict([
            ('id', task.id),
            ('Index',count),
            ('Creator', OrderedDict([
                ('id',task.creator.id),
                ('username',task.creator.username),
                ('name',task.creator.get_full_name()),
                ('email',task.creator.email)])),
            ('Lien', task.lien.id),
            ('Recipients', [OrderedDict([
                ('id',u.id),
                ('username',u.username),
                ('name',u.get_full_name()),
                ('email',u.email)]) for u in recipients]),
            ('Created', str(task.timestamp)),
            ('Description', task.description),
            ('Goal Date', str(task.goal_date)),
            ('Status', task.status),
        ])
        task_list.append(taskObject)
        count += 1

    json_response = simplejson.dumps({
        "tasks": task_list,
        "status_opts": status_types,
        "admin_ops": is_admin
    })
    
    return HttpResponse(json_response, mimetype="application/json")



def get_specific_notification_tasks(request):

    from collections import OrderedDict
    
    # admin can see all task entries by all users.
    user = request.user
    # is_admin = check_is_admin(5)
    is_admin = check_is_admin(user.id)

    # this post updates single task and sends back response with updated info.
    if request.method == 'POST': 
        post_dict = json.loads(request.body)

        # ugh we had a weird whitepace issue........ lets do it in case, for all.
        before = str(post_dict['before'].strip())
        after = str(post_dict['after'].strip())
        county = str(post_dict['county'].strip())
        creator = str(post_dict['creator'].strip())
        task_status = str(post_dict['status'].strip())

        if post_dict['before'] != 'None' and post_dict['after'] != 'None':
            before = post_dict['before']
            after = post_dict['after']
        else:
            before = None
            after = None


        # options for task status
        status_types = [
            {'value': 'completed', 'label': 'Completed'},
            {'value': 'request_review', 'label': 'Request For Review'},
            {'value': 'not_complete', 'label': 'Not Complete'}
        ]

        # verify if adim is logged in.
        if not is_admin['verified']:
            tasks = user.notificationreport_set.all()
        else:
            tasks = NotificationReport.objects.all()


        if before and after:
            # We have to convert from string to datetime
            before = datetime.strptime(str(before), '%Y-%m-%d').strftime('%Y-%m-%d')
            after = datetime.strptime(str(after), '%Y-%m-%d').strftime('%Y-%m-%d')

            tasks = tasks.filter(goal_date__range=(before, after))
        
        if str(county) != 'None':
            county = post_dict['county']
            county = County.objects.filter(name = str(county))
            tasks = tasks.filter(lien__county = county)

        
        if str(creator) != 'None':
            creator = post_dict['creator']
            creator = User.objects.filter(username = str(creator))
            tasks = tasks.filter(creator = creator)

        if str(task_status) != 'None':
            status = post_dict['status']
            tasks = tasks.filter(status = status)

        task_list = [];
        count = 0
        
        # building initial task data on request.
        for task in tasks:
            recipients = task.notification_group.all()
            
            taskObject = OrderedDict([
                ('id', task.id),
                ('Index',count),
                ('Creator', OrderedDict([
                    ('id',task.creator.id),
                    ('username',task.creator.username),
                    ('name',task.creator.get_full_name()),
                    ('email',task.creator.email)])),
                ('Lien', task.lien.id),
                ('Recipients', [OrderedDict([
                    ('id',u.id),
                    ('username',u.username),
                    ('name',u.get_full_name()),
                    ('email',u.email)]) for u in recipients]),
                ('Created', str(task.timestamp)),
                ('Description', task.description),
                ('Goal Date', str(task.goal_date)),
                ('Status', task.status),
            ])
            task_list.append(taskObject)
            count += 1

        json_response = simplejson.dumps({
            "tasks": task_list,
            "status_opts": status_types,
            "admin_ops": is_admin
        })
        
        return HttpResponse(json_response, mimetype="application/json")

    else:
        json_response = simplejson.dumps({
            'welp': "welp"
        })
        return HttpResponse(json_response, mimetype="application/json")





def check_is_admin(id):
    '''
    Check if the current logged in user is our administrator.
    ''' 

    # real
    admin_ids = [10,85]

    # wwbtc testing
    # admin_ids = [10]

    user_data = []
    for user_id in admin_ids:
        user_data.append({ 
            "name": User.objects.filter(id=user_id).values('username')[0], 
            "id" : user_id })
    return { "verified": id in admin_ids, "data": user_data }

def get_second_statuses(request):
    post_dict = request.POST.dict()

    status_id = int(post_dict['status_id']);

    json_data = simplejson.dumps({
        'success': True,
        'choices': None
    });

    if status_id == 74:
        
        json_data = simplejson.dumps({
            'success': True,
            'choices' : '1,24,65,None'
        });
    elif status_id == 75:
        json_data = simplejson.dumps({
            'success': True,
            'choices' : '42,43,45,60,61,None'
        });
    elif status_id == 76:
        json_data = simplejson.dumps({
            'success': True,
            'choices' : '3,5,44,None'
        });

    return HttpResponse(json_data, mimetype="application/json")


def get_third_statuses(request):
    post_dict = request.POST.dict()

    status_id = int(post_dict['status_id']);
    
    json_data = simplejson.dumps({
        'success': True,
        'choices': None
    });

    # Payments/Foreclosure Prospect
    if status_id == 1 or status_id == 24:
        json_data = simplejson.dumps({
            'success': True,
            'choices' : '38,49,50,None'
        });
    # Litigation/Foreclosure
    elif status_id == 3 or status_id == 44:
        json_data = simplejson.dumps({
            'success': True,
            'choices' : '35,47,51,52,53,54,62,56,63,59,64,66,67,68,69,70,72,73,74,75,76,77,78,79,80,81,82,83,None'
        });
    # Bankruptcy
    elif status_id == 5:
        json_data = simplejson.dumps({
            'success': True,
            'choices' : '16,58,59,None'
        });
    else:
        json_data = simplejson.dumps({
            'success': True,
            'choices' : 'None'
        });

    return HttpResponse(json_data, mimetype="application/json")


def get_write_off_mc_sale_report(request):
    schema = {
        'passcode': {'type': 'string', 'required': True},
        'start': {'required': False},
        'end': {'required': False}
    }

    post_dict = request.POST.dict()


    
    if request.POST:
        if not Validator(schema).validate(post_dict):
            json_data = simplejson.dumps({
                "success": False,
                "msg": "Missing required information from schema %s" % str(schema)
            })
            return HttpResponse(json_data, mimetype="application/json")
        if post_dict["passcode"] != passcode:
            json_data = simplejson.dumps({
                'success': False,
                'msg': 'Passcode is invalid.'
            })
            return HttpResponse(json_data, mimetype="application/json")

        
        start_date = post_dict['start'] if 'start' in post_dict else None
        end_date = post_dict['end'] if 'end' in post_dict else None

        # TODO:: LIENOWNER REMOVE HARDCODE
        data = get_write_off_mc_sale_data(int(3), start_date=start_date, end_date=end_date)


        json_data = simplejson.dumps({
            'success': True,
            'data': data
        })
        return HttpResponse(json_data, mimetype="application/json")
    else:
        json_data = simplejson.dumps({
            "success": False,
            "msg": "No post data."
        })
        return HttpResponse(json_data, mimetype="application/json")


        

def get_tax_lien_report(request):
    schema = {
        'passcode': {'type': 'string', 'required': True}
    }

    post_dict = request.POST.dict()
    if request.POST:
        if not Validator(schema).validate(post_dict):
            json_data = simplejson.dumps({
                "success": False,
                "msg": "Missing required information from schema %s" % str(schema)
            })
            return HttpResponse(json_data, mimetype="application/json")
        if post_dict["passcode"] != passcode:
            json_data = simplejson.dumps({
                'success': False,
                'msg': 'Passcode is invalid.'
            })
            return HttpResponse(json_data, mimetype="application/json")

        redemptive_values = Lien.objects.redemptive_value_calcs_ich()

        product_pool_size_redemptive = redemptive_values['total']
        product_pool_size_face = Lien.objects.face_value_ich()
        lien_count = Lien.objects.dashboard_liens_ich().count()
        average_lien_face_value = Lien.objects.average_face_value_ich()
        minimum_lien_face_value = Lien.objects.min_face_value_ich()
        maximum_lien_face_value = Lien.objects.max_face_value_ich()
        minimum_redemptive_value = redemptive_values['minimum']
        maximum_redemptive_value = redemptive_values['maximum']
        average_redemptive_value = redemptive_values['average']

        distribution = redemptive_values['distribution']

        tax_year_breakdown = Lien.objects.tax_year_breakdown_ich()

        #additional_liens = Lien.objects.additional_liens()

        county_breakdown = Lien.objects.county_breakdown_ich()

        uniqueTotal = 0;
        lienTotal = 0;

        for c in county_breakdown:
            lienTotal += c['count'];
            countyObject = County.objects.filter(name=c['county']);
            for co in countyObject:
                liens = Lien.objects.filter(county=co.id);
                liens = liens.filter(date_paid__isnull=True);
                liens = liens.order_by('map_number').values('map_number').distinct();
                liens = liens.exclude(lien_owner__id=1);
                liens = liens.exclude(status__name="Refunded");
                c['unique'] = liens.count();
                uniqueTotal += liens.count();

        payout_breakdown = PayoutBreakdownICH().get_totals()

        interest_rates = [
            {'display': '<= 5%', 'count': 0, 'percentage': 0},
            {'display': '5 - 8%', 'count': 0, 'percentage': 0},
            {'display': '8 - 11%', 'count': 0, 'percentage': 0},
            {'display': '11 - 14%', 'count': lien_count, 'percentage': 100},
            {'display': '14 - 17%', 'count': 0, 'percentage': 0},
            {'display': '17 - 20%', 'count': 0, 'percentage': 0},
            {'display': '> 20%', 'count': 0, 'percentage': 0},
        ]
			
        
        json_data = simplejson.dumps({
            'success': True,
            'product_pool_size_redemptive': int(product_pool_size_redemptive),     
            'product_pool_size_face': int(product_pool_size_face),
            'lien_count': int(lien_count),
            'average_lien_face_value': int(average_lien_face_value),
            'minimum_lien_face_value': int(minimum_lien_face_value),
            'maximum_lien_face_value': int(maximum_lien_face_value),
            'minimum_redemptive_value': int(minimum_redemptive_value),
            'maximum_redemptive_value': int(maximum_redemptive_value),
            'average_redemptive_value': int(average_redemptive_value),
            'distribution': distribution,
            'tax_year_breakdown': tax_year_breakdown,
            #'additional_liens': additional_liens,
            'interest_rates': interest_rates,
            'county_breakdown': county_breakdown,
            'payout_breakdown': payout_breakdown,
            'unique_total': int(uniqueTotal),
            'lien_total' : int(lienTotal),
        })
        return HttpResponse(json_data, mimetype="application/json")
    else:
        json_data = simplejson.dumps({
            "success": False,
            "msg": "No post data."
        })
        return HttpResponse(json_data, mimetype="application/json")


def add_property_inspection_fee(request):
    schema = {
        'lien_id': {'type': 'string', 'required': True},
        'passcode': {'type': 'string', 'required': True},
        'inspection_date': {'type': 'string'}
    }
    post_dict = request.POST.dict()
    if request.POST:
        if not Validator(schema).validate(post_dict):
            json_data = simplejson.dumps({
                "success": False,
                "msg": "Missing required information from schema %s" % str(schema)
            })
            return HttpResponse(json_data, mimetype="application/json")
        if post_dict["passcode"] != passcode:
            json_data = simplejson.dumps({
                'success': False,
                'msg': 'Passcode is invalid.'
            })
            return HttpResponse(json_data, mimetype="application/json")

        # Pull information out of dictionary
        expense_date = post_dict.get("inspection_date", datetime.now().strftime('%Y-%m-%d'))
        # Create Foreclosure Attorney Billing
        foreclosure_attny_expense_class = ExpenseClass.objects.get(id=16)
        lien = get_object_or_404(Lien, id=post_dict["lien_id"])

        prev_inspection_expenses = Expense.objects.filter(
            lien__id=post_dict["lien_id"],
            expense_class__id=16,
            note__icontains='inspection'
        )
        if len(prev_inspection_expenses) == 0:
            new_expense = Expense(
                note="Inspection of property",
                lien=lien,
                expense_class=foreclosure_attny_expense_class,
                expense_date=expense_date,
                amount=Decimal(125)
            )
            new_expense.save()
            json_data = simplejson.dumps({
                'success': True,
                'expense_id': new_expense.id
            })
        else:
            first_expense_id = prev_inspection_expenses[0].id
            json_data = simplejson.dumps({
                'success': True,
                'expense_id': first_expense_id
            })
        return HttpResponse(json_data, mimetype="application/json")
    else:
        json_data = simplejson.dumps({
            "success": False,
            "msg": "No post data."
        })
        return HttpResponse(json_data, mimetype="application/json")

def mark_letters_as_sent(request):
    '''Marks a range of letters as sent'''
    # Check if letter type is supported
    schema = {
        'liens_to_mark_sent': {
            'type': 'list',
            'required': True,
            'schema': {'type': 'integer'}
        },
        'letter_type': {
            'type': 'string',
            'required': True,
            'allowed': letterToProp.keys()
        }
    }

    post_dict = json.loads(request.body, parse_float=Decimal)
    validation = Validator(schema)
    if request.POST:
        if not validation.validate(post_dict):
            err = validation.errors
            json_data = simplejson.dumps({
                "success": False,
                "msg": "Missing required information from schema: %s" % str(err)
            })
            return HttpResponse(json_data, mimetype="application/json")
        else:
            markLetterListSent(
                post_dict['liens_to_mark_sent'],
                post_dict['letter_type']
            )
        json_data = simplejson.dumps({
            "success": True,
            "lien_ids": post_dict['liens_to_mark_sent']
        })
        return HttpResponse(json_data, mimetype="application/json")


@user_passes_test(lambda u: u.is_staff)
def lien_info(request):
    '''
    Handles requests for a list of liens and specific properties.

    The request comes in as a JSON POST request, with the following
    structure:

        `{"lien_ids": [1100, 1101], "fields": ["id", "assessed_value"]}`

    This view fetches the liens by the ids in `lien_ids`, and returns a JSON
    object containing only the fields and values listed in `fields`.
    '''
    docFields = ['pva_card', 'topo_map', 'tax_sheet']
    if not request.method == 'POST' or not request.body:
        json_response = simplejson.dumps({
            "success": False,
            "msg": "Not a POST request! You need to post the lien ids you want."
        })
    else:
        post_dict = json.loads(request.body, parse_float=Decimal)
        def to_str(attr, field):
            '''Sanely converts attrs for json.'''
            attr_type = type(attr)
            if field == 'related_lien_ids':
                return_val = [str(int(x)) for x in attr]
                return return_val
            elif field in docFields:
                return attr
            else:
                return str(attr)
        def lien_to_dict(lien):
            return {
                field: to_str(getattr(lien, field), field)
                for field in post_dict['fields']
            }
        requested_liens = {
            lien_id: lien_to_dict(Lien.objects.get(pk=lien_id))
            for lien_id in post_dict['lien_ids']
        }
        json_response = simplejson.dumps({
            'success': True,
            'result': requested_liens
        })
    return HttpResponse(json_response, mimetype="application/json")

# @user_passes_test(lambda u: u.is_staff)
def inspection_notes(request):
    '''
    Gets inspection notes based upon an id
    '''
    if not request.method == 'POST' or not request.body:
        json_response = simplejson.dumps({
            "success": False,
            "msg": "Not a POST request! You need to post the lien ids you want."
        })
    else:
        post_dict = json.loads(request.body, parse_float=Decimal)
        lien_id = post_dict['lien_id']
        notes = InspectionNote.objects.filter(lien=lien_id)

        note_list = []
        for note in notes:
            note_list.append(note.body)

        json_response = simplejson.dumps({
            "success": True,
            "result": note_list
        })
    return HttpResponse(json_response, mimetype="application/json")







    

# @user_passes_test(lambda u: u.is_staff)
# def get_filter_options(request):
def get_attorney_list(request):
    '''
    Gets list of attornies
    '''
    attornies = Attorney.objects.all()
    attorney_list = []


    # Lets do this one first, just so its on top. Its our fall back.
    attyObject = {
        'label': 'All Attorneys',
        'value': ''    
    }
    attorney_list.append(attyObject)

    # Now we will loop through all attornies in the system and append to the list
    for attorney in attornies: 
        attyObject = {
            'label': attorney.name,
            'value': attorney.name
        }
        attorney_list.append(attyObject)

        
    

    json_response = simplejson.dumps({
        "attornies": attorney_list
    })

    return HttpResponse(json_response, mimetype="application/json")


def get_investors_list(request):
    '''
    Gets list of investors
    '''

    
    # investors = Investor.objects.all()

    # MSCP and ICH only
    investors = Investor.objects.filter(Q(id = 1) | Q(id = 3))
    investor_list = []


    # Lets do this one first, just so its on top. Its our fall back.
    invObject = {
        'label': 'All Investors',
        'value': ''    
    }
    investor_list.append(invObject)

    # Now we will loop through all investors in the system and append to the list
    for investor in investors:
        # let's use initials if available
        if not investor.nickname:
            inv_name = investor.name
        else:
            inv_name = investor.nickname

        invObject = {
            'label': inv_name,
            'value': inv_name
        }

        investor_list.append(invObject)

    json_response = simplejson.dumps({
        "investors": investor_list
    })

    return HttpResponse(json_response, mimetype="application/json")




@user_passes_test(lambda u: u.is_staff)
def auto_note_generator(request):
    '''
    Get lien data and automate the note process.
    '''
    schema = {
        'add_note_to_liens': {
            'type': 'list',
            'required': True,
            'schema': {'type': 'integer'}
        },
        'letter_type': {
            'type': 'string',
            'required': True,
            'allowed': letterToProp.keys()
        }
    }

    post_dict = json.loads(request.body, parse_float=Decimal)
    validation = Validator(schema)
    if request.POST:
        if not validation.validate(post_dict):
            err = validation.errors
            json_data = simplejson.dumps({
                "success": False,
                "msg": "Missing required information from schema: %s" % str(err)
            })
            return HttpResponse(json_data, mimetype="application/json")
        else:
            addAutomatedNote(
                post_dict['add_note_to_liens'],
                post_dict['letter_type'],
                request.user
            )
            json_data = simplejson.dumps({
                "success": True,
                "lien_ids": post_dict['add_note_to_liens']
            })
        return HttpResponse(json_data, mimetype="application/json")




def generate_labels(request):
    '''Collect data to generate mailing labels.'''
    # Check if letter type is supported
    schema = {
        'liens_to_generate_labels': {
            'type': 'list',
            'required': True,
            'schema': {'type': 'integer'}
        },
        'letter_type': {
            'type': 'string',
            'required': True,
            'allowed': letterToProp.keys()
        },
        'counties': {
            'type': 'string',
        } 
    }
    
    post_dict = json.loads(request.body, parse_float=Decimal)
    validation = Validator(schema)
    if request.POST:
        if not validation.validate(post_dict):
            err = validation.errors
            json_data = simplejson.dumps({
                "success": False,
                "msg": "Missing required information from schema: %s" % str(err)
            })
            return HttpResponse(json_data, mimetype="application/json")
        else:
            filename = createLabels(
                post_dict['liens_to_generate_labels'],
                post_dict['letter_type'],
                post_dict['counties'],
            )
        json_data = simplejson.dumps({
            "success": True,
            "lien_ids": post_dict['liens_to_generate_labels'],
            "labels": filename
        })
        return HttpResponse(json_data, mimetype="application/json")

@user_passes_test(lambda u: u.is_staff)
def edit_note(request, id):

    if request.POST:
        current_user = request.user
        timestamp = datetime.now()

        
        # retrieve the note object.
        try:
            note = Note.objects.get(pk=id)
            post_dict = simplejson.loads(request.body)
        except Note.DoesNotExist:
            json_data = simplejson.dumps({
                'success': False,
                'error': 'Note object doesn\'t exist.'
            })

            return HttpResponse(json_data, mimetype="application/json")
        
        # setattr(note, 'body', post_dict['edit'])
        note.__dict__.update({ 'body': post_dict['edit'], 'editor_id':current_user.id, 'edited_at': timestamp })
        note.save()

        lien = Lien.objects.get(pk=note.lien_id)

        activity.create_update_log(
            lien = lien,
            user = request.user,
            object_id = note.id,
            object_revision_id = note.id,
            object_type = "Note"
        )


        json_data = simplejson.dumps({
            'success': True,
            'msg': 'Note has been updated.'
        })

    return HttpResponse(json_data, mimetype="application/json")