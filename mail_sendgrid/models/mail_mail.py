# -*- encoding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2015-2016 Compassion CH (http://www.compassion.ch)
#    Releasing children from poverty in Jesus' name
#    @author: Roman Zoller, Emanuel Cino <ecino@compassion.ch>
#
#    The licence is in the file __openerp__.py
#
##############################################################################
import base64
import logging
import re
import time

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Attachment, CustomArg, Content, \
    Personalization, Substitution, Mail

from openerp import models, fields, api, exceptions, tools, _
from openerp.tools.config import config


STATUS_OK = 202

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    """ Add SendGrid related fields so that they dispatch in all
    subclasses of mail.message object
    """
    _inherit = 'mail.message'

    ##########################################################################
    #                                 FIELDS                                 #
    ##########################################################################
    body_text = fields.Text(help='Text only version of the body')
    sent_date = fields.Datetime(copy=False)
    substitution_ids = fields.Many2many(
        'sendgrid.substitution', string='Substitutions', copy=True)
    sendgrid_template_id = fields.Many2one(
        'sendgrid.template', 'Sendgrid Template')
    send_method = fields.Char(compute='_compute_send_method')

    ##########################################################################
    #                             FIELDS METHODS                             #
    ##########################################################################
    @api.multi
    def _compute_send_method(self):
        """ Check whether to use traditional send method, sendgrid or disable.
        """
        send_method = self.env['ir.config_parameter'].get_param(
            'mail_sendgrid.send_method', 'traditional')
        for email in self:
            email.send_method = send_method


class OdooMail(models.Model):
    """ Email message sent through SendGrid """
    _inherit = 'mail.mail'

    ##########################################################################
    #                                 FIELDS                                 #
    ##########################################################################
    tracking_email_ids = fields.One2many(
        'mail.tracking.email', 'mail_id', string='Registered events',
        readonly=True)
    click_count = fields.Integer(
        compute='_compute_tracking', store=True, readonly=True)
    opened = fields.Boolean(
        compute='_compute_tracking', store=True, readonly=True)
    tracking_event_ids = fields.One2many(
        'mail.tracking.event', compute='_compute_events')

    @api.depends('tracking_email_ids', 'tracking_email_ids.click_count',
                 'tracking_email_ids.state')
    def _compute_tracking(self):
        for email in self:
            email.click_count = sum(email.tracking_email_ids.mapped(
                'click_count'))
            opened = len(email.tracking_email_ids.filtered(
                lambda t: t.state == 'opened'))
            email.opened = opened > 0

    def _compute_events(self):
        for email in self:
            email.tracking_event_ids = email.tracking_email_ids.mapped(
                'tracking_event_ids')

    ##########################################################################
    #                             PUBLIC METHODS                             #
    ##########################################################################
    @api.multi
    def send(self, auto_commit=False, raise_exception=False):
        """ Override send to select the method to send the e-mail. """
        for email in self:
            send_method = email.send_method
            if send_method == 'traditional':
                return super(OdooMail, email).send(
                    auto_commit, raise_exception)
            elif send_method == 'sendgrid':
                return email.send_sendgrid()
            else:
                _logger.warning(
                    "Traditional e-mails are disabled. Please remove system "
                    "parameter mail_sendgrid.send_method if you want to send "
                    "e-mails through your configured SMTP.")
                email.write({'state': 'exception'})
        return True

    @api.multi
    def send_sendgrid(self):
        """ Use sendgrid transactional e-mails : e-mails are sent one by
        one. """
        api_key = config.get('sendgrid_api_key')
        if not api_key:
            raise exceptions.Warning(
                'ConfigError',
                _('Missing sendgrid_api_key in conf file'))

        sg = SendGridAPIClient(apikey=api_key)
        for email in self:
            try:
                response = sg.client.mail.send.post(
                    request_body=email._prepare_sendgrid_data())
            except Exception as e:
                _logger.error(e.read())
                continue

            status = response.status_code
            msg = response.body

            if status == STATUS_OK:
                _logger.info(str(msg))
                email._track_sendgrid_emails()
                email.write({
                    'sent_date': fields.Datetime.now(),
                    'state': 'sent'
                })
                # Update message body in associated message, which will be
                # shown in message history view for linked odoo object
                # defined through fields model and res_id. This will allow
                # tracking from the thread.
                message = email.mail_message_id
                message_vals = {
                    'body': email.body_html
                }
                if not message.subtype_id:
                    message_vals['subtype_id'] = self.env.ref(
                        'mail.mt_comment').id
                if not message.notified_partner_ids:
                    message_vals['notified_partner_ids'] = [
                        (6, 0, email.recipient_ids.ids)]
                message.write(message_vals)
                # Commit changes since e-mail was sent
                self.env.cr.commit()
            else:
                _logger.error("Failed to send email: {}".format(str(msg)))

    ##########################################################################
    #                             PRIVATE METHODS                            #
    ##########################################################################
    def _prepare_sendgrid_data(self):
        self.ensure_one()
        s_mail = Mail()
        s_mail.set_from(Email(self.email_from))
        s_mail.set_reply_to(Email(self.reply_to))
        s_mail.add_custom_arg(CustomArg('odoo_id', self.message_id))
        html = self.body_html or ' '

        p = re.compile(r'<.*?>')  # Remove HTML markers
        text_only = self.body_text or p.sub('', html.replace('<br/>', '\n'))

        s_mail.add_content(Content("text/plain", text_only))
        s_mail.add_content(Content("text/html", html))

        test_address = config.get('sendgrid_test_address')

        # TODO For now only one personalization (transactional e-mail)
        personalization = Personalization()
        personalization.set_subject(self.subject or ' ')
        if not test_address:
            if self.email_to:
                personalization.add_to(Email(self.email_to))
            for recipient in self.recipient_ids:
                personalization.add_to(Email(recipient.email))
            if self.email_cc:
                personalization.add_cc(Email(self.email_cc))
        else:
            _logger.info('Sending email to test address {}'.format(
                test_address))
            personalization.add_to(Email(test_address))
            self.email_to = test_address

        if self.sendgrid_template_id:
            s_mail.set_template_id(self.sendgrid_template_id.remote_id)

        for substitution in self.substitution_ids:
            personalization.add_substitution(Substitution(
                substitution.key, substitution.value))

        s_mail.add_personalization(personalization)

        for attachment in self.attachment_ids:
            s_attachment = Attachment()
            # Datas are not encoded properly for sendgrid
            s_attachment.set_content(base64.b64encode(base64.b64decode(
                attachment.datas)))
            s_attachment.set_filename(attachment.name)
            s_mail.add_attachment(s_attachment)

        return s_mail.get()

    def _track_sendgrid_emails(self):
        """ Create tracking e-mails after successfully sent with Sendgrid. """
        self.ensure_one()
        m_tracking = self.env['mail.tracking.email'].sudo()
        track_vals = self._prepare_sendgrid_tracking()
        for recipient in tools.email_split_and_format(self.email_to):
            track_vals['recipient'] = recipient
            m_tracking.create(track_vals)
        for partner in self.recipient_ids:
            track_vals.update({
                'partner_id': partner.id,
                'recipient': partner.email,
            })
            m_tracking.create(track_vals)

    def _prepare_sendgrid_tracking(self):
        ts = time.time()
        return {
            'name': self.subject,
            'timestamp': '%.6f' % ts,
            'time': fields.Datetime.now(),
            'mail_id': self.id,
            'mail_message_id': self.mail_message_id.id,
            'sender': self.email_from,
        }
