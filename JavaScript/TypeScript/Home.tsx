import * as React from "react";
import { splitEvery, head, tail } from 'ramda';
import { getConfig } from '../../utils/getLiens';
import { getStoredViewHistory } from '../../utils/getLocalState';
import {
    getInspection,
    InspectionResponse,
} from '../../utils/getInspections';
import { applyAction } from './state';
import { chunksOf } from 'fp-ts/lib/Array';

import {
    HomeProps, HomeState, HomeAction,
    LiensById, UpdateState
} from './Home.types';
import { fetchLiensById, getAttorneyList, getCompositeCalculations } from '../../api/api';
import {
    loadConfig, closeModal, loadLiens, loadInspection, 
    loadAttorneyOptionsToState,loadCompositeCalculations
} from './actions';

import { TableView } from '../Table/View';
import { Hero } from '../Hero/Hero';
import ModalSwitch from './ModalSwitch';
import { prepend } from 'ramda';

import '../../css/table.css';

// async function attorneyFetcher(
//     updateState: UpdateState
//     ){
//     const attyList = await getAttorneyList();
//     updateState(loadAttorneyOptionsToState(attyList))
// }

async function lienFetcher(
    state: HomeState,
    updateState: UpdateState
): Promise<HomeState> {
    const lienIds: number[] = state.config.lienIds;
    const partitionedIds: Array<number[]> = splitEvery(30, lienIds);
    const displayFields = state.config.displayFields;

    async function iterator(
        remainingLiens: Array<number[]>,
        stateMod: HomeState
    ): Promise<HomeState> {
        const nextBatch: number[] = head(remainingLiens);
        if (!nextBatch) {
            return stateMod;
        }
        const liensById: LiensById = await fetchLiensById(
            nextBatch,
            displayFields
        )
        const oldLiensById: LiensById = state.liensById;
        const newLiensById: LiensById = { ...oldLiensById, ...liensById };
        const newState: HomeState = { ...stateMod, ...{ liensById: newLiensById } }
        // Side effects!
        updateState(loadLiens(liensById))

        return iterator(
            tail(remainingLiens),
            newState
        )
    }
    return iterator(partitionedIds, state);
}

async function inspectionFetcher(
    lienIds: number[],
    updateState: UpdateState
) {
    const lienBatches = chunksOf(lienIds, 10);
    const hitApi = async (lienBatch: number[]) => {
        const apiResults: InspectionResponse[]
            = await Promise.all(
                lienBatch.map(getInspection)
            );
        function stateUpdater(
            result: InspectionResponse
        ): void {
            updateState(loadInspection(result));
        }
        return apiResults.map(stateUpdater);
    }
    for (var i = 0; i < lienBatches.length; i++) {
        await hitApi(lienBatches[i]);
    }
}

const trace = (x: any) => {
    return x;
}

const compositeCalculationFetcher = async (
    lienIds: number[], 
    updateState: UpdateState
    ) => {
    const calculations = await getCompositeCalculations(lienIds)
    updateState(loadCompositeCalculations(calculations));
}

// 'HelloProps' describes the shape of props.
// State is never set so we use the '{}' type.
export class Home extends React.Component<HomeProps, HomeState> {
    constructor(props: HomeProps) {
        super(props);
        this.state = {
            errors: [],
            liensById: {},
            pagination: 30,
            page: 0,
            inspections: {},
            realFilters: {
                columnFilters: {
                    
                }
            },
            filter: {
                field: 'id',
                reverse: false
            },
            selectionOptions: {},
            compositeCalculations: [],
            viewHistory: getStoredViewHistory(),
            modal: {
                name: '',
                active: false,
                opts: {}
            },
            loadComplete: false,
        };
    }
    componentDidMount(): void {
        this.loadInitState();
    }

    updateState(action: HomeAction): HomeState {
        const newState = applyAction(this.state, action);
        this.setState(newState);
        // console.log(newState)
        return newState;
    }
    loadInitState(): void {
        /* Pulls config off DOM, loads it into state. */
        const lienFetch = (s: HomeState) => {
            lienFetcher(s, this.updateState.bind(this));
            return s;
        }
        const inspectionFetch = (s: HomeState) => {
            const { lienIds } = s.config;
            inspectionFetcher(lienIds, this.updateState.bind(this));
        }
        const compositeCalculationFetch = (config: any) => {
            const lienIds = config.value.lienIds
            compositeCalculationFetcher(lienIds, this.updateState.bind(this))
        }
        const config = getConfig()
            .map(loadConfig)
            .map(this.updateState.bind(this)) // Side effect!
            .map(lienFetch)                   // Side effect!
            .map(trace)
            .map(inspectionFetch);
            
        // pull composite calculations on load.
        compositeCalculationFetch(getConfig());
    }
    tableView() {
        const {
            config, liensById, page, pagination, selectionOptions
        } = this.state;

        if (!this.state.config) {
            return null;
        }
        return (
            <div>
                <TableView
                    liensById={liensById}
                    homeState={this.state}
                    displayFields={config && config.displayFields}
                    filterFields={config && config.filterFields}
                    lienIds={config && config.lienIds}
                    page={page}
                    pagination={pagination}
                    editableFields={config.editableFields}
                    otherFields={config.otherFields}
                    updateState={this.updateState.bind(this)}
                    filter={this.state.filter}
                    search={this.state.search}
                    selectionOptions={selectionOptions}
                    calculations={this.state.compositeCalculations}
                    loadComplete={this.state.loadComplete}
                />
            </div>
        );
    }
    modal() {
        const modalName = this.state.modal.name;
        const showModal = this.state.modal.active;
        const closeModalHandler = (e: React.MouseEvent) => {
            e.preventDefault();
            const updateState = this.updateState.bind(this);
            updateState(closeModal());
        };
        return (
            <ModalSwitch modalName={modalName}
                homeState={this.state}
                showModal={showModal}
                closeModal={closeModalHandler}
                updateState={this.updateState.bind(this)}
            />

        );
    }
    render() {
        const { config } = this.state;
        return (
            <div className="lien-list-home">
                <Hero title={config && config.pageTitle}
                    subtitle={config && config.pageSubtitle}
                />
                {this.tableView()}
                {this.modal()}
            </div>
        );
    }
}
