from django.core.exceptions import ValidationError

class ContractService:
    def __init__(self, contract):
        self.contract = contract

    def post(self):
        if self.contract.status == 'active':
            raise ValidationError("Договір уже активний.")
        self.contract.status = 'active'
        self.contract.save()

    def unpost(self):
        if self.contract.status != 'active':
            raise ValidationError("Договір не активний.")
        self.contract.status = 'draft'
        self.contract.save()
