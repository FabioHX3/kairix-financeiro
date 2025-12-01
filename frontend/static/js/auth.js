// Configuração da API
const API_URL = window.location.origin;

// Gerenciamento de Token
class AuthService {
    static setToken(token) {
        localStorage.setItem('token', token);
    }

    static getToken() {
        return localStorage.getItem('token');
    }

    static removeToken() {
        localStorage.removeItem('token');
    }

    static isAuthenticated() {
        return !!this.getToken();
    }

    static async getCurrentUser() {
        try {
            const response = await fetch(`${API_URL}/api/auth/me`, {
                headers: {
                    'Authorization': `Bearer ${this.getToken()}`
                }
            });

            if (!response.ok) {
                this.removeToken();
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('Erro ao obter usuário:', error);
            return null;
        }
    }

    static async login(email, senha) {
        try {
            const response = await fetch(`${API_URL}/api/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, senha })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Erro ao fazer login');
            }

            const data = await response.json();
            this.setToken(data.access_token);
            return data;
        } catch (error) {
            throw error;
        }
    }

    static async cadastrar(dados) {
        try {
            const response = await fetch(`${API_URL}/api/auth/cadastro`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(dados)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Erro ao cadastrar');
            }

            return await response.json();
        } catch (error) {
            throw error;
        }
    }

    static logout() {
        this.removeToken();
        window.location.href = '/login';
    }
}

// Helper para fazer requisições autenticadas
async function fetchAPI(url, options = {}) {
    const token = AuthService.getToken();

    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` })
        }
    };

    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };

    const response = await fetch(`${API_URL}${url}`, mergedOptions);

    if (response.status === 401) {
        AuthService.logout();
        return;
    }

    return response;
}

// Verifica autenticação nas páginas protegidas
function requireAuth() {
    if (!AuthService.isAuthenticated()) {
        window.location.href = '/login';
    }
}

// Redireciona se já estiver autenticado (para páginas de login/cadastro)
function redirectIfAuthenticated() {
    if (AuthService.isAuthenticated()) {
        window.location.href = '/dashboard';
    }
}
