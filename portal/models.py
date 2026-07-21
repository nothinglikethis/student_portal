from django.db import models


class Student(models.Model):
    ug_number      = models.CharField(max_length=20, unique=True)
    name           = models.CharField(max_length=100)
    password       = models.CharField(max_length=128, blank=True, default="")
    active_session_key = models.CharField(max_length=40, null=True, blank=True)
    division       = models.CharField(max_length=10, choices=[('AIML', 'AIML'), ('AIRO', 'AIRO')], null=True, blank=True)

    # 4-part checklist — set to True by the webhook when each form is submitted
    personal_done  = models.BooleanField(default=False)
    academic_done  = models.BooleanField(default=False)
    residence_done = models.BooleanField(default=False)
    documents_done = models.BooleanField(default=False)

    # 8 individual document flags — set granularly by the documents webhook
    doc_passport  = models.BooleanField(default=False)
    doc_signature = models.BooleanField(default=False)
    doc_aadhaar   = models.BooleanField(default=False)
    doc_apaar     = models.BooleanField(default=False)
    doc_tenth     = models.BooleanField(default=False)
    doc_twelfth   = models.BooleanField(default=False)
    doc_tc_lc     = models.BooleanField(default=False)
    doc_caste     = models.BooleanField(default=False)

    created_at    = models.DateTimeField(auto_now_add=True)

    # Maps each doc field to its human-readable label
    DOC_FIELDS = [
        ("doc_passport",  "Passport Size Photo"),
        ("doc_signature", "Signature"),
        ("doc_aadhaar",   "Aadhaar Card"),
        ("doc_apaar",     "APAAR ID"),
        ("doc_tenth",     "10th Marksheet"),
        ("doc_twelfth",   "12th Marksheet"),
        ("doc_tc_lc",     "TC / Leaving Certificate"),
        ("doc_caste",     "Caste Certificate"),
    ]

    class Meta:
        ordering = ["ug_number"]

    def __str__(self):
        return f"{self.ug_number} — {self.name}"

    @property
    def admission_status(self):
        """Derive status from checklist booleans — no separate status field needed."""
        all_forms = self.personal_done and self.academic_done and self.residence_done
        all_docs = all(getattr(self, field) for field, label in self.DOC_FIELDS)
        
        if all_forms and all_docs:
            return "APPROVED"
            
        any_form = self.personal_done or self.academic_done or self.residence_done
        any_doc = any(getattr(self, field) for field, label in self.DOC_FIELDS)
        
        if any_form or any_doc:
            return "HOLD"
            
        return "PENDING"

    @property
    def pending_docs(self):
        """Return list of incomplete top-level checklist steps."""
        pending = []
        if not self.personal_done:
            pending.append("Personal Details Form")
        if not self.academic_done:
            pending.append("Academic Details Form")
        if not self.residence_done:
            pending.append("Residence Details Form")
        if not self.documents_done:
            pending.append("Mandatory Documents")
        return pending

    @property
    def pending_individual_docs(self):
        """Return list of (field, label) tuples for documents not yet submitted."""
        return [(field, label) for field, label in self.DOC_FIELDS if not getattr(self, field)]

    @property
    def submitted_individual_docs(self):
        """Return list of (field, label) tuples for documents already submitted."""
        return [(field, label) for field, label in self.DOC_FIELDS if getattr(self, field)]
