# NEUXO Backend API (Selected Services)

This document is generated from the service handlers in:
- `neuxo_backend/services/company_services.py`
- `neuxo_backend/services/company_details_services.py`
- `neuxo_backend/services/event_services.py`
- `neuxo_backend/services/watchlist_services.py`
- `neuxo_backend/services/email_services.py`
- `neuxo_backend/services/gen_email_services.py`

Base URL
- {BASE_URL}/api

Auth
- All endpoints below use `requireLogin` unless stated otherwise.

Conventions
- Path params are shown as `{id}` or `{contact_id}`.
- Query params are listed per endpoint. Shared params are listed below.

Shared Query Parameters
- `page` (int): Page number
- `limit` (int): Page size
- `search_key` (string): Search keyword
- `start_date` (string, format: YYYY-MM-DD HH:MM:SS)
- `end_date` (string, format: YYYY-MM-DD HH:MM:SS)

Email Query Parameters (used by email list endpoints)
- `email_status` (string): REPLIED, SEEN, ERROR, SENT
- `email_count_start` (int): Minimum email count
- `email_count_end` (int): Maximum email count
- `last_activity_start_date` (string)
- `last_activity_end_date` (string)
- `follow_up_status` (string): Focused, Overdue, Upcoming
- `priority` (string): HIGH, MEDIUM, LOW
- `time_zone` (string): Default Asia/Saigon

---

## Matching Companies (company_services)

### GET /matching-companies/list
Query Params
- Shared Query Parameters
- `count_trigger` (int, enum: 1,2,3,4)
- `assignee` (string)
- `country` (string)
- `company_size` (string)
- `followers` (string)
- `industry` (string)
- `trigger` (string)
- `organization_type` (string)
- `category` (string)
- `company_email` (string)

Response 200
```json
{
    "message": "Success",
    "meta": {"columns": []},
    "pagination": {},
    "data": []
}
```


### GET /matching-companies/listCountryCompany
Response 200
```json
{
    "message": "Success",
    "data": {
        "list_country": [],
        "industry": [],
        "organization_type": [],
        "trigger": ["event", "funding", "news", "hiring"]
    }
}
```

### PUT /matching-companies/updateShowingColumns
Request Body
```json
{
    "name_columns": [
        {"name": "company_name", "is_show": true, "can_arrange": true}
    ]
}
```

Response 200
```json
{
    "message": "Success",
    "data": {"columns": []}
}
```

### GET /matching-companies/downloadMasterCompany
Response 200
- Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- File: matching_companies.xlsx

### GET /companies/field-column
Query Params
- `table` (string, optional)

Response 200
```json
{
    "message": "Success",
    "columns": []
}
```

### GET /companies/{id}
Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

---

## Company Details (company_details_services)

Note: `/companies/{id}` is defined in both company services and company details.

### GET /companies/{id}
Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

### POST /companies/addTwitter/{id}
Request Body
```json
{
    "url_twitter": "https://twitter.com/example"
}
```

Response 200
```json
{
    "message": "Success",
    "data": {"link_twitter": "https://twitter.com/example"}
}
```

### GET /companies/{id}/contact
Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### POST /companies/{id}/addContact
Request Body
```json
{
    "linkedin_url": "https://linkedin.com/in/example",
    "twitter_url": "https://twitter.com/example"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### PUT /companies/delete-contact/{id}
Response 200
```json
{
    "message": "Success"
}
```

### POST /companies/contact/{id}/addEmail
Request Body
```json
{
    "email": "person@example.com"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### DELETE /companies/contact/removeEmail/{id}
Response 200
```json
{
    "message": "Success"
}
```

### PUT /companies/contact/{contact_id}/updateEmail/{id}
Request Body
```json
{
    "email": "person@example.com"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /getEventsByCompanyID/{id}
Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### GET /getJobsByCompanyID/{id}
Query Params
- Shared Query Parameters

Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### GET /getContactsByCompanyID/{id}
Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### GET /getFundingByCompanyID/{id}
Query Params
- Shared Query Parameters

Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### GET /getTriggerByCompanyID/{id}
Query Params
- Shared Query Parameters

Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

### POST /company/notify/seen
Request Body
```json
{
    "ids": "id1,id2"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /company/{id}/notify
Response 200
```json
{
    "message": "Success",
    "new_notify": 0
}
```

---

## Events (event_services)

### GET /events/list
Query Params
- `start_date` (string)
- `end_date` (string)
- `page` (int)
- `limit` (int)
- `search_key` (string)
- `main_event` (string)
- `country` (string)
- `status` (string, enum: UPCOMING, ONGOING, PAST)

Response 200
```json
{
    "message": "Success",
    "pagination": {},
    "data": []
}
```

### GET /events/country-parent
Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

### GET /events/{id}
Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

### GET /events/{id}/guests
Query Params
- `event_id` (string, required)
- `search_key` (string)
- `role` (string)
- `country` (string)
- `category` (string)
- `email_status` (string)
- `headquarter` (string)
- `page` (int)
- `limit` (int)
- `sortByVal` (string)
- `orderByVal` (string, enum: ASC, DESC)

Response 200
```json
{
    "message": "Success",
    "pagination": {},
    "data": []
}
```

### GET /events/columns/guests
Query Params
- `event_id` (string, required)

Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### PUT /events/guests/updateNote
Request Body
```json
{
    "id": "guest_id",
    "note": "Note"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### PUT /events/guests/updateEmail
Request Body
```json
{
    "id": "guest_id",
    "email": "guest@example.com"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /events/company-link/{id}
Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### GET /events/download
Query Params
- Shared Query Parameters

Response 200
- Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- File: Events.xlsx

### GET /events/download/companies
Path Params
- `id` (string)

Response 200
- Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- File: CompaniesInEvent.xlsx

### GET /events/download/guests
Query Params
- `start_date` (string)
- `end_date` (string)

Response 200
- Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- File: Guests.xlsx

---

## Watchlist (watchlist_services)

### PUT /watchlist/add
Request Body
```json
{
    "id": "company_id"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### PUT /watchlist/remove
Request Body
```json
{
    "ids": "id1,id2"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /watchlist/list
Query Params
- Shared Query Parameters
- `search_key` (string)
- `icp_id` (string)
- `company_size` (string)
- `followers` (string)
- `country` (string)

Response 200
```json
{
    "message": "Success",
    "pagination": {},
    "data": []
}
```

### PUT /watchlist/PIN
Request Body
```json
{
    "company_id": "company_id"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### PUT /watchlist/company/editNote
Request Body
```json
[
    {"company_id": "id", "note": "text"}
]
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /watchlist/notify
Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### POST /watchlist/seenAll
Request Body
```json
{
    "type": "contact",
    "filter": "NEWS,HIRING,EVENT,LINKEDIN,TWITTER,SUB_DOMAIN"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /watchlist/contact/{id}/create-id-completions
Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

### GET /watchlist/company/{id}/create-id-completions
Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

### POST /watchlist/save-history-chat
Request Body
```json
{
    "model": "gpt-4o",
    "completion_id": "id",
    "messages": [
        {"role": "user", "content": "..."}
    ]
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /watchlist/contact/{id}/get-history-chat
Query Params
- Shared Query Parameters

Response 200
```json
{
    "message": "Success",
    "pagination": {},
    "data": []
}
```

### GET /watchlist/company/{id}/get-history-chat
Query Params
- Shared Query Parameters

Response 200
```json
{
    "message": "Success",
    "pagination": {},
    "data": []
}
```

### PUT /watchlist/delete-history-chat
Request Body
```json
{
    "completion_id": "id"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### POST /watchlist/edit-subject-chat
Request Body
```json
{
    "completion_id": "id",
    "subject": "New subject"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /watchlist/mention/{id}/people
Query Params
- `offset` (int)
- `limit` (int)
- `range_time` (string, example: SEVEN_DAYS)

Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### GET /watchlist/mention/{id}
Query Params
- `offset` (int)
- `limit` (int)
- `filter` (string, example: NEWS,HIRING,EVENT,LINKEDIN,TWITTER,SUB_DOMAIN)

Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### GET /watchlist/mention
Query Params
- `offset` (int)
- `limit` (int)
- `filter` (string, example: NEWS,HIRING,EVENT,LINKEDIN,TWITTER,SUB_DOMAIN)
- `type` (string, example: contact)

Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### POST /watchlist/company/{id}/addGuestMention
Request Body
```json
{
    "linkedin_url": "https://linkedin.com/in/example",
    "twitter_url": "https://twitter.com/example",
    "email": "guest@example.com"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### POST /watchlist/company/{id}/addGuestAvailableMention
Request Body
```json
{
    "guest_id": "guest_id"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### PUT /watchlist/company/{id}/removeGuestMention
Request Body
```json
{
    "guest_id": "guest_id"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /watchlist/company/{id}
Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### PUT /watchlist/company/{id}/updateCompany
Request Body
```json
{
    "twitter_url": "https://twitter.com/example",
    "website": "https://example.com",
    "country": "US"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /watchlist/company/{id}/getDetailInfo
Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

### POST /watchlist/company/checkHadOtherWatchlist
Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

### POST /watchlist/company/checkHadCreateManual
Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

### GET /watchlist/company/{id}/newNotifyToday
Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

### PUT /watchlist/company/contact/{id}/updateContact
Request Body
```json
{
    "twitter_url": "https://twitter.com/example",
    "linkedin_url": "https://linkedin.com/in/example"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /watchlist/company/contact/{id}
Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### GET /watchlist/ICP/list
Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### PUT /watchlist/ICP/save
Request Body
```json
{
    "company_id": "company_id",
    "icp_id": "icp_id"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /admin/watchlist/mention/{id}/people
Query Params
- `offset` (int)
- `limit` (int)
- `user_id` (string, optional)

Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### GET /admin/watchlist/contact/{id}
Query Params
- `user_id` (string, optional)

Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### GET /admin/watchlist/mention/{id}
Query Params
- `offset` (int)
- `limit` (int)
- `filter` (string)
- `user_id` (string, required)

Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### GET /admin/watchlist/all-member
Query Params
- `search_key` (string)
- `list_icp` (string)
- `list_user_id` (string)
- `page` (int)
- `limit` (int)

Response 200
```json
{
    "message": "Success",
    "pagination": {},
    "data": []
}
```

### GET /admin/watchlist/{id}/list
Query Params
- `search_key` (string)
- `start_date` (string)
- `end_date` (string)
- `page` (int)
- `limit` (int)
- `icp_id` (string)
- `company_size` (string)
- `followers` (string)
- `country` (string)

Response 200
```json
{
    "message": "Success",
    "pagination": {},
    "data": []
}
```

---

## Email Management (email_services)

### PUT /mail/addAccount
Request Body
```json
{
    "email": "user@example.com",
    "password": "app_password"
}
```

Response 200
```json
{
    "message": "Email account added successfully. Mailbox crawl has been queued and will run in the background."
}
```

### GET /mail/getAllConversation
Query Params
- Shared Query Parameters
- Email Query Parameters

Response 200
```json
{
    "message": "Success",
    "pagination": {},
    "data": []
}
```

### GET /mail/get-list-email-tracking
Query Params
- Shared Query Parameters
- Email Query Parameters
- `follow_up_start_date` (string)
- `follow_up_end_date` (string)
- `source` (string, example: replied, unresponsive, prospected)

Response 200
```json
{
    "message": "Success",
    "pagination": {},
    "data": []
}
```

### GET /mail/getMailDetails
Query Params
- Shared Query Parameters
- `target_mail` (string, required)

Response 200
```json
{
    "message": "Success",
    "pagination": {},
    "data": []
}
```

### PUT /mail/updateRecord
Request Body
```json
{
    "target_email": "target@example.com",
    "note": "Follow up next week",
    "priority": "HIGH"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### PUT /mail/setFollowUpDateForReplied
Request Body
```json
{
    "target_email": "target@example.com",
    "follow_up_date": "2024-12-31 10:00:00"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### GET /mail/getSignatures
Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### PUT /mail/putSignature
Request Body
```json
{
    "signature_name": "Default",
    "signature_html": "<p>Best regards</p>",
    "email_account_id": "optional",
    "signature_id": "optional"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### DELETE /mail/deleteSignature/{id}
Response 200
```json
{
    "message": "Success"
}
```

### POST /email/template/create
Request Body
```json
{
    "template_name": "Intro",
    "template_subject": "Hello",
    "template_content": "...",
    "attachments": []
}
```

Response 200
```json
{
    "message": "Template created successfully",
    "data": {}
}
```

### GET /email/template/list
Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### PUT /email/template/update/{id}
Request Body
```json
{
    "template_name": "Intro",
    "template_subject": "Hello",
    "template_content": "...",
    "attachments": []
}
```

Response 200
```json
{
    "message": "Success"
}
```

### DELETE /email/template/delete/{id}
Response 200
```json
{
    "message": "Success"
}
```

### GET /email/template/{id}
Response 200
```json
{
    "message": "Success",
    "data": {
        "id": "...",
        "template_name": "...",
        "template_subject": "...",
        "template_content": "...",
        "attachments": []
    }
}
```

### POST /automate/email/create-sequence
Request Body
```json
{
    "signature": "signature_id",
    "list_email": ["user@example.com"],
    "custom_sequence": [1, 3, 7],
    "campaign_name": "Optional",
    "source": "company",
    "enable_bimonthly": false,
    "max_email_bimonthly": 0,
    "user_hot_trigger": false,
    "hot_trigger_condition": [],
    "event_id": "optional"
}
```

Response 200
```json
{
    "message": "Create sequence successful!",
    "data": {}
}
```

### GET /automate/email/preview-email
Query Params
- `email` (string, required)
- `sequence_id` (string, required)
- `source` (string)
- `event_id` (string)

Response 200
```json
{
    "message": "Success",
    "data": []
}
```

### POST /automate/email/submit-sequence
Request Body
```json
{
    "sequence_id": "id",
    "content_email": [
        {
            "email": "target@example.com",
            "data": [
                {"stepNum": 1, "subject": "Hi", "content": "..."}
            ]
        }
    ],
    "event_id": "optional"
}
```

Response 200
```json
{
    "message": "Success"
}
```

### POST /automate/email/check-email-sent
Request Body
```json
{
    "list_email": ["target@example.com"]
}
```

Response 200
```json
{
    "message": "Success",
    "data": {}
}
```

---

## Gen-Email (gen_email_services)

### POST /gen-email/generate
Request Body
```json
{
    "sender_name": "John",
    "recipient_name": "Alice",
    "recipient_email": "alice@example.com",
    "company_name": "TechCorp",
    "event_name": "Web Summit 2024",
    "event_location": "Lisbon",
    "event_dates": "2024-11-01 to 2024-11-03",
    "email_type": "first_email",
    "custom_instructions": "Optional"
}
```

Response 200
```json
{
    "subject": "...",
    "content": "...",
    "success": true
}
```

### POST /gen-email/generate-bulk
Request Body
```json
{
    "sender_name": "John",
    "recipients": [
        {"name": "Alice", "email": "alice@example.com", "company_name": "TechCorp"}
    ],
    "event_name": "Web Summit 2024",
    "event_location": "Lisbon",
    "event_dates": "2024-11-01 to 2024-11-03",
    "email_type": "first_email",
    "custom_instructions": "Optional"
}
```

Response 200
```json
{
    "results": [
        {"email": "alice@example.com", "subject": "...", "content": "...", "success": true}
    ],
    "total": 1,
    "successful": 1,
    "failed": 0
}
```

### POST /gen-email/validate
Request Body
```json
{
    "subject": "Hello",
    "content": "Email body"
}
```

Response 200
```json
{
    "valid": true,
    "warnings": [],
    "word_count": 100
}
```

### GET /gen-email/types
Response 200
```json
{
    "email_types": [
        {"type": "first_email", "name": "First Outreach", "description": "..."},
        {"type": "follow_up", "name": "Follow-up", "description": "..."},
        {"type": "custom", "name": "Custom Email", "description": "..."}
    ]
}
```
