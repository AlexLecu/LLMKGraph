export function getLocalName(uri: string): string {
    const hashIndex = uri.lastIndexOf('#');
    if (hashIndex !== -1) return uri.substring(hashIndex + 1);
    const slashIndex = uri.lastIndexOf('/');
    if (slashIndex !== -1) return uri.substring(slashIndex + 1);
    return uri;
  }
  
  let statusTimeout: number | null = null;
  export function clearStatusTextAfterDelay(setter: (msg: string) => void, delay = 5000) {
    if (statusTimeout) clearTimeout(statusTimeout);
    statusTimeout = setTimeout(() => {
      setter('');
    }, delay);
  }
  