# -*- encoding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2014 Compassion CH (http://www.compassion.ch)
#    Releasing children from poverty in Jesus' name
#    @author: Emanuel Cino <ecino@compassion.ch>
#
#    The licence is in the file __openerp__.py
#
##############################################################################

from openerp import models, fields, api
from openerp.osv import orm

from openerp.addons.child_compassion.models.compassion_hold import \
    HoldType

from lxml import etree


class EndContractWizard(models.TransientModel):
    _name = 'end.contract.wizard'

    end_date = fields.Datetime(
        required=True, default=fields.Datetime.now)
    contract_id = fields.Many2one(
        'recurring.contract', 'Contract',
        default=lambda self: self.env.context.get('active_id'))
    child_id = fields.Many2one(
        'compassion.child', 'Child',
        default=lambda self: self._get_child_id())
    end_reason = fields.Selection('_get_end_reason', required=True)
    do_transfer = fields.Boolean('I want to transfer the child')
    transfer_country_id = fields.Many2one(
        'compassion.global.partner', 'Country')
    has_new_hold = fields.Boolean('Keep child on hold', default=True)
    hold_expiration_date = fields.Datetime(
        default=lambda s: s.env[
            'compassion.hold'].get_default_hold_expiration(
            HoldType.SPONSOR_CANCEL_HOLD),
        required=True)

    @api.model
    def _get_child_id(self):
        # Retrieve the id of the sponsored child
        contract = self.env['recurring.contract'].browse(
            self.env.context.get('active_id'))
        return contract.child_id.id if contract.child_id else False

    def _get_end_reason(self):
        return self.env['recurring.contract'].get_ending_reasons()

    @api.v7
    def fields_view_get(self, cr, user, view_id=None, view_type='form',
                        context=None, toolbar=False, submenu=False):
        res = super(EndContractWizard, self).fields_view_get(
            cr, user, view_id, view_type, context, toolbar, submenu)
        # If there is no child in contract, hide field
        if view_type == 'form' and not self._get_child_id(cr, user, context):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='child_id']"):
                node.set('invisible', "1")
                orm.setup_modifiers(node, res['fields']['child_id'])
            res['arch'] = etree.tostring(doc)

        return res

    @api.multi
    def end_contract(self):
        self.ensure_one()
        contract = self.contract_id
        child = contract.child_id
        has_hold = self.has_new_hold

        # When sponsorship activated, the hold is removed.
        if not child.hold_id:
            if has_hold:
                self.env['icp.reservation'].create({
                    'name': 'single beneficiary reservation',
                    'expiration_date': self.hold_expiration_date,
                    'hold_expiration_date': self.hold_expiration_date,
                    'number_of_beneficiaries': '1',
                    'primary_owner': self.env.uid,
                    'icp_id': child.project_id.id,
                    'child_id': child.id
                })
            child.write({'active': False, 'state': 'F'})
        else:
            if has_hold:
                # Update the hold
                child.hold_id.write({
                    'type': HoldType.SPONSOR_CANCEL_HOLD.value,
                    'expiration_date': self.hold_expiration_date
                })
            # The sponsorship was not active
            if not has_hold:
                child.hold_id.active = False
                child.write({'active': False, 'state': 'F', 'hold_id': False})

        # Terminate contract
        contract.write({
            'end_reason': self.end_reason,
            'end_date': self.end_date,
            'transfer_partner_id': self.transfer_country_id.id,
            # 'hold_expiration_date': self.hold_expiration_date,
        })
        contract.signal_workflow('contract_terminated')

        return True
