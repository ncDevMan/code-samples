import { reduce, keys, assoc, pipe } from 'ramda';
import { LiensById, selectOptions, CompCalculations } from '../features/Home/Home.types';

interface InspectionNoteOpts {
    lien_id: number,
    note: string
}

async function createInspectionNote(
    opts: InspectionNoteOpts
) {
    console.log('inspection note tried to create')
    try {
        const response = await fetch('/lien/update_inspection_note/', {
            method: 'POST',
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(opts)
        });
        console.log(response);
        const payload = await response.json()
        console.log('this is the payload:', payload)
    } catch (e) {
        const err = await e;
        console.log(err)
    }
}
/**
 * Attorney selection list api
 */
async function getAttorneyList(){
    const response = await fetch('/api/v1/get_attorney_list/')
    const payload = await response.json(); 
    console.log('hitting attorney api');   
    return payload;
}
/**
 * Investor selection list api
 */
async function getInvestorList(){
    const response = await fetch('/api/v1/get_investors_list/')
    const payload = await response.json();    
    return payload;
}
/**
 * Get Composite Calculations for liens.
 */
async function getCompositeCalculations(lienIds: number[]) {
    const response = await fetch('/api/v1/get_composite_calculations/', {
        method: 'POST',
        headers: {
            "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
            lien_ids: lienIds,
        })
    })
    console.log('did we get to the api?')
    const payload = await response.json();
    const result = payload.calculations;
    
    return result;
}

async function fetchInspectionNotes(
    lienId: number
) {
    /* Gets inspection notes from server. */
    const response = await fetch('/api/v1/inspection_note/', {
        method: 'POST',
        headers: {
            "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
            lien_id: lienId,
        })
    })
    const payload = await response.json();
    const result = payload.result;
    return result;
}

async function fetchLiensById(
    lienIds: Array<number>,
    fields: Array<string>
): Promise<LiensById> {
    /* Gets liens from server. */
    const response = await fetch('/api/v1/lien_info/', {
        method: 'POST',
        headers: {
            "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
            lien_ids: lienIds,
            fields
        })
    })
    // TODO io-ts here
    const payload = await response.json();
    const result: LiensById = payload.result;
    return result;
}

interface ModifyLienOpts {
    lien_id: number,
    field_to_mutate: string,
    val_to_set: string | number | boolean
}
async function modifyLien(
    opts: ModifyLienOpts,
    successCb: Function,
    failCb: Function
) {
    /* Modifies liens on Django backend.

       TODO Optimistic updates. */
    try {
        const response = await fetch('/lien/modify_lien/', {
            method: 'POST',
            headers: {
                "Content-Type": "application/json",
            },
            credentials: "include",
            body: JSON.stringify(opts)
        });
        const payload = await response.json()
        if (!payload.success) {
            failCb(payload);
        }
        successCb(payload);
    } catch (e) {
        const err = await e;
        failCb(err);
    }
}

export { fetchLiensById, modifyLien, createInspectionNote, fetchInspectionNotes, getAttorneyList, getInvestorList, getCompositeCalculations };
