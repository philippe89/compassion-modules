# -*- encoding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2016 Compassion CH (http://www.compassion.ch)
#    Releasing children from poverty in Jesus' name
#    @author: Michael Sandoz <sandozmichael@hotmail.com>
#
#    The licence is in the file __openerp__.py
#
##############################################################################
from openerp.addons.message_center_compassion.mappings.base_mapping import \
    OnrampMapping
from datetime import datetime


class ChilpoolCreateHoldMapping(OnrampMapping):
    """
    Childpool mapping for reserving available children from GMC.
    """
    ODOO_MODEL = 'compassion.hold'
    MAPPING_NAME = "create_hold"

    CONNECT_MAPPING = {
        'Beneficiary_GlobalID': ('child_id.global_id', 'compassion.child'),
        "BeneficiaryState": 'type',
        'EstimatedNoMoneyYieldRate': 'no_money_yield_rate',
        'HoldEndDate': 'expiration_date',
        "HoldID": 'hold_id',
        'HoldYieldRate': 'yield_rate',
        'PrimaryHoldOwner': 'primary_owner.name',
        'SecondaryHoldOwner': 'secondary_owner',
        "SourceCode": 'source_code',
        'Channel_Name': 'channel',
    }

    FIELDS_TO_SUBMIT = {
        'Beneficiary_GlobalID': None,
        'BeneficiaryState': None,
        'EstimatedNoMoneyYieldRate': None,
        'HoldEndDate': None,
        "HoldID": None,
        'HoldYieldRate': None,
        "IsSpecialHandling": None,
        'PrimaryHoldOwner': None,
        'SecondaryHoldOwner': None,
        "SourceCode": None,
        'Channel_Name': None,
        "GlobalPartner_ID": None,
    }

    CONSTANTS = {
        "GlobalPartner_ID": "CH",
        "IsSpecialHandling": False,
    }

    def _process_connect_data(self, connect_data):
        # Set end date to correct format for Connect
        if 'HoldEndDate' in connect_data:
            endDateStr = connect_data.get('HoldEndDate')
            endDate = datetime.strptime(endDateStr, "%Y-%m-%d %H:%M:%S")
            connect_data['HoldEndDate'] = endDate.strftime(
                "%Y-%m-%dT%H:%M:%SZ")


class ChilpoolReleaseHoldMapping(ChilpoolCreateHoldMapping):
    """
        Childpool mapping for realease children on GMC.
        """
    MAPPING_NAME = "release_hold"

    FIELDS_TO_SUBMIT = {
        'Beneficiary_GlobalID': None,
        "HoldID": None,
        "GlobalPartner_ID": None,
    }


class ReservationToHoldMapping(OnrampMapping):
    ODOO_MODEL = 'compassion.hold'
    MAPPING_NAME = 'reservation_to_hold'

    CONNECT_MAPPING = {
        'BeneficiaryOrder_HoldID': 'hold_id',
        'Beneficiary_GlobalID': ('child_id.global_id', 'compassion.child'),
        'HoldExpirationDate': 'expiration_date',
        'PrimaryOwner': 'primary_owner.name',
        'ReservationHoldType': 'type',
        'ReservationID': ('reservation_id.reservation_id', 'icp.reservation'),
        'SecondaryOwner': 'secondary_owner',
        # Not used in Odoo
        'BeneficiaryOrder_ID': None,
        'GlobalPartner_ID': None,
        'ICP_ID': None,
        'ReservationType_Name': None,
        'CampaignEventID': None,
    }
