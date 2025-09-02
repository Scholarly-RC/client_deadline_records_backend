# Client Documents API Documentation

## Overview

The Client Documents API provides comprehensive file management capabilities for client-related documents. This feature allows administrators and staff to upload, manage, and download client documents with proper access controls and audit logging.

## Base URL

```
http://your-domain.com/api/
```

## Authentication

All API endpoints require authentication using JWT tokens. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

## API Endpoints

### 1. List Client Documents

**GET** `/api/client-documents/`

Retrieve a paginated list of client documents with filtering and search capabilities.

#### Query Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `page` | integer | Page number for pagination | `?page=2` |
| `page_size` | integer | Number of items per page (max 100) | `?page_size=20` |
| `client` | integer | Filter by client ID | `?client=123` |
| `uploaded_by` | integer | Filter by uploader ID | `?uploaded_by=456` |
| `uploaded_at__gte` | date | Filter documents uploaded after date | `?uploaded_at__gte=2024-01-01` |
| `uploaded_at__lte` | date | Filter documents uploaded before date | `?uploaded_at__lte=2024-12-31` |
| `search` | string | Search in title, description, client name, uploader name | `?search=tax` |
| `ordering` | string | Order by field (prefix with `-` for descending) | `?ordering=-uploaded_at` |

#### Available Ordering Fields
- `title`
- `uploaded_at`
- `updated_at`
- `client__name`

#### Response

```json
{
  "count": 25,
  "next": "http://localhost:8000/api/client-documents/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "client": 123,
      "client_name": "ABC Corporation",
      "title": "Tax Return 2024",
      "description": "Annual tax return documents",
      "document_file": "http://localhost:8000/uploads/client_documents/tax_return_2024.pdf",
      "uploaded_by": 456,
      "uploaded_by_name": "John Doe",
      "file_size": "2.5 MB",
      "file_extension": "PDF",
      "uploaded_at": "2024-01-15 10:30 AM",
      "updated_at": "2024-01-15 10:30 AM"
    }
  ]
}
```

#### Permissions
- **Admin users**: Can view all documents
- **Staff users**: Can only view documents for clients they created

---

### 2. Get Client Document Details

**GET** `/api/client-documents/{id}/`

Retrieve detailed information about a specific document.

#### Response

```json
{
  "id": 1,
  "client": 123,
  "client_name": "ABC Corporation",
  "title": "Tax Return 2024",
  "description": "Annual tax return documents including schedules",
  "document_file": "http://localhost:8000/uploads/client_documents/tax_return_2024.pdf",
  "uploaded_by": 456,
  "uploaded_by_name": "John Doe",
  "file_size": "2.5 MB",
  "file_extension": "PDF",
  "uploaded_at": "2024-01-15 10:30 AM",
  "updated_at": "2024-01-15 10:30 AM"
}
```

#### Error Responses

```json
// 404 Not Found
{
  "detail": "Not found."
}

// 403 Forbidden
{
  "detail": "You do not have permission to perform this action."
}
```

---

### 3. Upload Client Document

**POST** `/api/client-documents/`

Upload a new document for a client. Use `multipart/form-data` for file uploads.

#### Request Body (Form Data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `client` | integer | Yes | Client ID |
| `title` | string | Yes | Document title (max 255 chars) |
| `description` | string | No | Document description |
| `document_file` | file | Yes | The document file to upload |

#### Example Request

```javascript
const formData = new FormData();
formData.append('client', '123');
formData.append('title', 'Tax Return 2024');
formData.append('description', 'Annual tax return documents');
formData.append('document_file', fileInput.files[0]);

fetch('/api/client-documents/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token
  },
  body: formData
});
```

#### Response

```json
{
  "id": 1,
  "client": 123,
  "client_name": "ABC Corporation",
  "title": "Tax Return 2024",
  "description": "Annual tax return documents",
  "document_file": "http://localhost:8000/uploads/client_documents/tax_return_2024.pdf",
  "uploaded_by": 456,
  "uploaded_by_name": "John Doe",
  "file_size": "2.5 MB",
  "file_extension": "PDF",
  "uploaded_at": "2024-01-15 10:30 AM",
  "updated_at": "2024-01-15 10:30 AM"
}
```

#### Validation Errors

```json
{
  "client": ["This field is required."],
  "title": ["This field is required."],
  "document_file": ["No file was submitted."]
}
```

---

### 4. Update Client Document

**PUT/PATCH** `/api/client-documents/{id}/`

Update document metadata (title, description). File cannot be changed after upload.

#### Request Body

```json
{
  "title": "Updated Tax Return 2024",
  "description": "Updated annual tax return documents with corrections"
}
```

#### Response

```json
{
  "id": 1,
  "client": 123,
  "client_name": "ABC Corporation",
  "title": "Updated Tax Return 2024",
  "description": "Updated annual tax return documents with corrections",
  "document_file": "http://localhost:8000/uploads/client_documents/tax_return_2024.pdf",
  "uploaded_by": 456,
  "uploaded_by_name": "John Doe",
  "file_size": "2.5 MB",
  "file_extension": "PDF",
  "uploaded_at": "2024-01-15 10:30 AM",
  "updated_at": "2024-01-15 11:45 AM"
}
```

---

### 5. Delete Client Document

**DELETE** `/api/client-documents/{id}/`

Delete a document and its associated file.

#### Response
- **204 No Content**: Document successfully deleted
- **404 Not Found**: Document not found
- **403 Forbidden**: No permission to delete

---

### 6. Download Client Document

**GET** `/api/client-documents/{id}/download/`

Download the actual document file.

#### Response
- Returns the file as a binary download with appropriate headers
- Content-Disposition header includes original filename

#### Error Responses

```json
// 404 Not Found
{
  "error": "Document not found"
}

// 403 Forbidden
{
  "error": "You don't have permission to download this document"
}
```

---

### 7. Get Documents by Client

**GET** `/api/client-documents/by-client/?client_id={client_id}`

Get all documents for a specific client.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `client_id` | integer | Yes | The client ID to get documents for |

#### Response

```json
[
  {
    "id": 1,
    "client": 123,
    "client_name": "ABC Corporation",
    "title": "Tax Return 2024",
    "description": "Annual tax return documents",
    "document_file": "http://localhost:8000/uploads/client_documents/tax_return_2024.pdf",
    "uploaded_by": 456,
    "uploaded_by_name": "John Doe",
    "file_size": "2.5 MB",
    "file_extension": "PDF",
    "uploaded_at": "2024-01-15 10:30 AM",
    "updated_at": "2024-01-15 10:30 AM"
  },
  {
    "id": 2,
    "client": 123,
    "client_name": "ABC Corporation",
    "title": "Financial Statement 2024",
    "description": "Year-end financial statements",
    "document_file": "http://localhost:8000/uploads/client_documents/financial_statement_2024.pdf",
    "uploaded_by": 456,
    "uploaded_by_name": "John Doe",
    "file_size": "1.8 MB",
    "file_extension": "PDF",
    "uploaded_at": "2024-01-20 02:15 PM",
    "updated_at": "2024-01-20 02:15 PM"
  }
]
```

---

## Frontend Implementation Guide

### 1. React/JavaScript Implementation

#### File Upload Component

```jsx
import React, { useState } from 'react';
import axios from 'axios';

const DocumentUpload = ({ clientId, onUploadSuccess }) => {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    document_file: null
  });
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        setError('File size must be less than 10MB');
        return;
      }
      // Validate file type
      const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
      if (!allowedTypes.includes(file.type)) {
        setError('File type not supported. Please upload PDF, DOC, DOCX, JPG, or PNG files.');
        return;
      }
      setFormData({ ...formData, document_file: file });
      setError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.document_file) {
      setError('Please select a file to upload');
      return;
    }

    setUploading(true);
    setError('');

    try {
      const uploadData = new FormData();
      uploadData.append('client', clientId);
      uploadData.append('title', formData.title);
      uploadData.append('description', formData.description);
      uploadData.append('document_file', formData.document_file);

      const response = await axios.post('/api/client-documents/', uploadData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      onUploadSuccess(response.data);
      setFormData({ title: '', description: '', document_file: null });
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="document-upload-form">
      <div className="form-group">
        <label htmlFor="title">Document Title *</label>
        <input
          type="text"
          id="title"
          value={formData.title}
          onChange={(e) => setFormData({ ...formData, title: e.target.value })}
          required
          placeholder="Enter document title"
        />
      </div>

      <div className="form-group">
        <label htmlFor="description">Description</label>
        <textarea
          id="description"
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          placeholder="Enter document description (optional)"
          rows={3}
        />
      </div>

      <div className="form-group">
        <label htmlFor="file">Select File *</label>
        <input
          type="file"
          id="file"
          onChange={handleFileChange}
          accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
          required
        />
        {formData.document_file && (
          <div className="file-info">
            <small>Selected: {formData.document_file.name} ({(formData.document_file.size / 1024 / 1024).toFixed(2)} MB)</small>
          </div>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      <button type="submit" disabled={uploading}>
        {uploading ? 'Uploading...' : 'Upload Document'}
      </button>
    </form>
  );
};

export default DocumentUpload;
```

#### Document List Component

```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const DocumentList = ({ clientId }) => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    fetchDocuments();
  }, [clientId, searchTerm, currentPage]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        client: clientId,
        page: currentPage,
        page_size: 10
      });

      if (searchTerm) {
        params.append('search', searchTerm);
      }

      const response = await axios.get(`/api/client-documents/?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      setDocuments(response.data.results);
      setTotalPages(Math.ceil(response.data.count / 10));
    } catch (err) {
      setError('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (documentId, filename) => {
    try {
      const response = await axios.get(`/api/client-documents/${documentId}/download/`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      alert('Download failed');
    }
  };

  const handleDelete = async (documentId) => {
    if (!window.confirm('Are you sure you want to delete this document?')) {
      return;
    }

    try {
      await axios.delete(`/api/client-documents/${documentId}/`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      setDocuments(documents.filter(doc => doc.id !== documentId));
    } catch (err) {
      alert('Delete failed');
    }
  };

  if (loading) return <div>Loading documents...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="document-list">
      <div className="search-bar">
        <input
          type="text"
          placeholder="Search documents..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      <div className="document-grid">
        {documents.map(doc => (
          <div key={doc.id} className="document-card">
            <div className="document-header">
              <h3>{doc.title}</h3>
              <span className="file-type">{doc.file_extension}</span>
            </div>

            {doc.description && (
              <p className="description">{doc.description}</p>
            )}

            <div className="document-meta">
              <span>Size: {doc.file_size}</span>
              <span>Uploaded: {doc.uploaded_at}</span>
              <span>By: {doc.uploaded_by_name}</span>
            </div>

            <div className="document-actions">
              <button
                onClick={() => handleDownload(doc.id, doc.title)}
                className="btn-download"
              >
                Download
              </button>
              <button
                onClick={() => handleDelete(doc.id)}
                className="btn-delete"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(currentPage - 1)}
          >
            Previous
          </button>
          <span>Page {currentPage} of {totalPages}</span>
          <button
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage(currentPage + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default DocumentList;
```

### 2. Vue.js Implementation

#### File Upload Component

```vue
<template>
  <form @submit.prevent="handleSubmit" class="document-upload">
    <div class="form-group">
      <label for="title">Document Title *</label>
      <input
        v-model="form.title"
        type="text"
        id="title"
        required
        placeholder="Enter document title"
      />
    </div>

    <div class="form-group">
      <label for="description">Description</label>
      <textarea
        v-model="form.description"
        id="description"
        placeholder="Enter document description"
        rows="3"
      />
    </div>

    <div class="form-group">
      <label for="file">Select File *</label>
      <input
        ref="fileInput"
        type="file"
        @change="handleFileChange"
        accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
        required
      />
      <div v-if="selectedFile" class="file-info">
        Selected: {{ selectedFile.name }} ({{ fileSize }})
      </div>
    </div>

    <div v-if="error" class="error-message">{{ error }}</div>

    <button type="submit" :disabled="uploading">
      {{ uploading ? 'Uploading...' : 'Upload Document' }}
    </button>
  </form>
</template>

<script>
export default {
  name: 'DocumentUpload',
  props: {
    clientId: {
      type: Number,
      required: true
    }
  },
  emits: ['upload-success'],
  data() {
    return {
      form: {
        title: '',
        description: ''
      },
      selectedFile: null,
      uploading: false,
      error: ''
    };
  },
  computed: {
    fileSize() {
      if (!this.selectedFile) return '';
      return (this.selectedFile.size / 1024 / 1024).toFixed(2) + ' MB';
    }
  },
  methods: {
    handleFileChange(event) {
      const file = event.target.files[0];
      if (!file) return;

      // Validate file size
      if (file.size > 10 * 1024 * 1024) {
        this.error = 'File size must be less than 10MB';
        this.selectedFile = null;
        return;
      }

      // Validate file type
      const allowedTypes = [
        'application/pdf',
        'image/jpeg',
        'image/png',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      ];

      if (!allowedTypes.includes(file.type)) {
        this.error = 'File type not supported. Please upload PDF, DOC, DOCX, JPG, or PNG files.';
        this.selectedFile = null;
        return;
      }

      this.selectedFile = file;
      this.error = '';
    },

    async handleSubmit() {
      if (!this.selectedFile) {
        this.error = 'Please select a file to upload';
        return;
      }

      this.uploading = true;
      this.error = '';

      try {
        const formData = new FormData();
        formData.append('client', this.clientId);
        formData.append('title', this.form.title);
        formData.append('description', this.form.description);
        formData.append('document_file', this.selectedFile);

        const response = await this.$axios.post('/api/client-documents/', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        });

        this.$emit('upload-success', response.data);

        // Reset form
        this.form = { title: '', description: '' };
        this.selectedFile = null;
        this.$refs.fileInput.value = '';

      } catch (error) {
        this.error = error.response?.data?.detail || 'Upload failed';
      } finally {
        this.uploading = false;
      }
    }
  }
};
</script>
```

### 3. Angular Implementation

#### Document Service

```typescript
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ClientDocument {
  id: number;
  client: number;
  client_name: string;
  title: string;
  description: string;
  document_file: string;
  uploaded_by: number;
  uploaded_by_name: string;
  file_size: string;
  file_extension: string;
  uploaded_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ClientDocument[];
}

@Injectable({
  providedIn: 'root'
})
export class DocumentService {
  private apiUrl = '/api/client-documents';

  constructor(private http: HttpClient) {}

  getDocuments(params?: any): Observable<DocumentListResponse> {
    let httpParams = new HttpParams();

    if (params) {
      Object.keys(params).forEach(key => {
        if (params[key] !== null && params[key] !== undefined) {
          httpParams = httpParams.set(key, params[key]);
        }
      });
    }

    return this.http.get<DocumentListResponse>(this.apiUrl, { params: httpParams });
  }

  getDocument(id: number): Observable<ClientDocument> {
    return this.http.get<ClientDocument>(`${this.apiUrl}/${id}/`);
  }

  uploadDocument(formData: FormData): Observable<ClientDocument> {
    return this.http.post<ClientDocument>(this.apiUrl, formData);
  }

  updateDocument(id: number, data: Partial<ClientDocument>): Observable<ClientDocument> {
    return this.http.patch<ClientDocument>(`${this.apiUrl}/${id}/`, data);
  }

  deleteDocument(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}/`);
  }

  downloadDocument(id: number): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${id}/download/`, {
      responseType: 'blob'
    });
  }

  getDocumentsByClient(clientId: number): Observable<ClientDocument[]> {
    return this.http.get<ClientDocument[]>(`${this.apiUrl}/by-client/?client_id=${clientId}`);
  }
}
```

#### Upload Component

```typescript
import { Component, EventEmitter, Output } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { DocumentService } from '../services/document.service';

@Component({
  selector: 'app-document-upload',
  template: `
    <form [formGroup]="uploadForm" (ngSubmit)="onSubmit()" class="upload-form">
      <div class="form-group">
        <label for="title">Document Title *</label>
        <input
          type="text"
          id="title"
          formControlName="title"
          placeholder="Enter document title"
        />
      </div>

      <div class="form-group">
        <label for="description">Description</label>
        <textarea
          id="description"
          formControlName="description"
          placeholder="Enter document description"
          rows="3"
        ></textarea>
      </div>

      <div class="form-group">
        <label for="file">Select File *</label>
        <input
          type="file"
          id="file"
          (change)="onFileSelected($event)"
          accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
        />
        <div *ngIf="selectedFile" class="file-info">
          Selected: {{ selectedFile.name }} ({{ getFileSize() }})
        </div>
      </div>

      <div *ngIf="error" class="error-message">{{ error }}</div>

      <button type="submit" [disabled]="uploading || !uploadForm.valid">
        {{ uploading ? 'Uploading...' : 'Upload Document' }}
      </button>
    </form>
  `
})
export class DocumentUploadComponent {
  @Output() uploadSuccess = new EventEmitter<any>();

  uploadForm: FormGroup;
  selectedFile: File | null = null;
  uploading = false;
  error = '';

  constructor(
    private fb: FormBuilder,
    private documentService: DocumentService
  ) {
    this.uploadForm = this.fb.group({
      title: ['', Validators.required],
      description: ['']
    });
  }

  onFileSelected(event: any) {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file size
    if (file.size > 10 * 1024 * 1024) {
      this.error = 'File size must be less than 10MB';
      this.selectedFile = null;
      return;
    }

    // Validate file type
    const allowedTypes = [
      'application/pdf',
      'image/jpeg',
      'image/png',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ];

    if (!allowedTypes.includes(file.type)) {
      this.error = 'File type not supported. Please upload PDF, DOC, DOCX, JPG, or PNG files.';
      this.selectedFile = null;
      return;
    }

    this.selectedFile = file;
    this.error = '';
  }

  getFileSize(): string {
    if (!this.selectedFile) return '';
    return (this.selectedFile.size / 1024 / 1024).toFixed(2) + ' MB';
  }

  onSubmit() {
    if (!this.uploadForm.valid || !this.selectedFile) {
      this.error = 'Please fill all required fields and select a file';
      return;
    }

    this.uploading = true;
    this.error = '';

    const formData = new FormData();
    formData.append('client', '123'); // Replace with actual client ID
    formData.append('title', this.uploadForm.value.title);
    formData.append('description', this.uploadForm.value.description);
    formData.append('document_file', this.selectedFile);

    this.documentService.uploadDocument(formData).subscribe({
      next: (response) => {
        this.uploadSuccess.emit(response);
        this.uploadForm.reset();
        this.selectedFile = null;
        this.uploading = false;
      },
      error: (error) => {
        this.error = error.error?.detail || 'Upload failed';
        this.uploading = false;
      }
    });
  }
}
```

## Error Handling

### Common Error Scenarios

1. **Authentication Errors**
   ```json
   {
     "detail": "Authentication credentials were not provided."
   }
   ```

2. **Permission Errors**
   ```json
   {
     "detail": "You do not have permission to perform this action."
   }
   ```

3. **Validation Errors**
   ```json
   {
     "title": ["This field is required."],
     "document_file": ["The submitted file is empty."]
   }
   ```

4. **File Size Errors**
   ```json
   {
     "document_file": ["File size exceeds the maximum allowed size."]
   }
   ```

## Best Practices

### Frontend Implementation

1. **File Validation**
   - Always validate file size and type on the client side
   - Provide clear error messages for validation failures
   - Show upload progress for large files

2. **User Experience**
   - Use drag-and-drop for file uploads when possible
   - Show file previews for images
   - Provide clear feedback during upload process
   - Allow multiple file selection for batch uploads

3. **Error Handling**
   - Implement retry logic for failed uploads
   - Show user-friendly error messages
   - Handle network timeouts gracefully

4. **Performance**
   - Compress images before upload
   - Use pagination for large document lists
   - Implement lazy loading for file previews

### Security Considerations

1. **File Type Validation**
   - Validate file types on both client and server
   - Use allowlists rather than blocklists
   - Scan uploaded files for malware

2. **Access Control**
   - Implement proper role-based permissions
   - Validate user permissions before file operations
   - Use secure file storage with proper access controls

3. **Data Protection**
   - Encrypt sensitive documents at rest
   - Implement proper audit logging
   - Use secure HTTPS connections

## Testing

### API Testing with cURL

```bash
# List documents
curl -H "Authorization: Bearer <token>" \
     "http://localhost:8000/api/client-documents/"

# Upload document
curl -X POST \
     -H "Authorization: Bearer <token>" \
     -F "client=123" \
     -F "title=Test Document" \
     -F "document_file=@/path/to/file.pdf" \
     "http://localhost:8000/api/client-documents/"

# Download document
curl -H "Authorization: Bearer <token>" \
     -o downloaded_file.pdf \
     "http://localhost:8000/api/client-documents/1/download/"
```

### Unit Testing Example

```javascript
// Test file upload validation
describe('DocumentUpload Component', () => {
  it('should validate file size', () => {
    const largeFile = new File(['x'.repeat(11 * 1024 * 1024)], 'large.pdf');
    const { result } = renderHook(() => useFileValidation());

    expect(result.current.validateFile(largeFile)).toBe(false);
    expect(result.current.error).toContain('File size must be less than 10MB');
  });

  it('should validate file type', () => {
    const invalidFile = new File(['content'], 'test.exe', { type: 'application/x-msdownload' });
    const { result } = renderHook(() => useFileValidation());

    expect(result.current.validateFile(invalidFile)).toBe(false);
    expect(result.current.error).toContain('File type not supported');
  });
});
```

## Support

For additional support or questions about the Client Documents API:

- Check the API documentation at `/api/schema/swagger-ui/`
- Review the OpenAPI schema at `/api/schema/`
- Contact the development team for implementation assistance

---

*This documentation was generated for the Client Documents API feature. Last updated: January 2025*