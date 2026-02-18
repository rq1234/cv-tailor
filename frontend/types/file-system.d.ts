interface FileSystemDirectoryHandle {
  queryPermission(descriptor: { mode: string }): Promise<string>;
  requestPermission(descriptor: { mode: string }): Promise<string>;
  getDirectoryHandle(
    name: string,
    options?: { create?: boolean }
  ): Promise<FileSystemDirectoryHandle>;
  getFileHandle(
    name: string,
    options?: { create?: boolean }
  ): Promise<FileSystemFileHandle>;
}

interface FileSystemFileHandle {
  createWritable(): Promise<FileSystemWritableFileStream>;
}

interface FileSystemWritableFileStream extends WritableStream {
  write(data: Blob | BufferSource | string): Promise<void>;
  close(): Promise<void>;
}

interface Window {
  showDirectoryPicker(options?: {
    mode?: string;
  }): Promise<FileSystemDirectoryHandle>;
}
