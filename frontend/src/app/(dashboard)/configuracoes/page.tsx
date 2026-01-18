'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { User, Bell, Palette, Users, Bot, Loader2, Trash2, Plus, Save } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { useAuthStore } from '@/stores/auth-store'
import { useUpdateProfile, useChangePassword } from '@/hooks/use-auth'
import { usePreferences, useUpdatePreferences, usePatterns, useDeletePattern } from '@/hooks/use-preferences'
import { useCategories, useCreateCategory, useDeleteCategory } from '@/hooks/use-categories'
import { useFamilyMembers, useCreateFamilyMember, useDeleteFamilyMember } from '@/hooks/use-family'
import { profileSchema, changePasswordSchema, type ProfileFormData, type ChangePasswordFormData } from '@/lib/utils/validators'
import type { Categoria, MembroFamilia, UserPattern } from '@/types/models'

const personalityOptions = [
  { value: 'formal', label: 'Formal', description: 'Respostas diretas e profissionais' },
  { value: 'amigavel', label: 'Amigável', description: 'Tom casual e acolhedor' },
  { value: 'divertido', label: 'Divertido', description: 'Usa humor e emojis' },
]

export default function ConfiguracoesPage() {
  const { user } = useAuthStore()
  const [deleteCategory, setDeleteCategory] = useState<Categoria | undefined>()
  const [deleteMember, setDeleteMember] = useState<MembroFamilia | undefined>()
  const [deletePattern, setDeletePatternItem] = useState<UserPattern | undefined>()

  // Hooks
  const updateProfileMutation = useUpdateProfile()
  const changePasswordMutation = useChangePassword()
  const { data: preferences, isLoading: loadingPrefs } = usePreferences()
  const updatePrefsMutation = useUpdatePreferences()
  const { data: categories, isLoading: loadingCats } = useCategories()
  const createCategoryMutation = useCreateCategory()
  const deleteCategoryMutation = useDeleteCategory()
  const { data: familyMembers, isLoading: loadingFamily } = useFamilyMembers()
  const createFamilyMutation = useCreateFamilyMember()
  const deleteFamilyMutation = useDeleteFamilyMember()
  const { data: patterns, isLoading: loadingPatterns } = usePatterns()
  const deletePatternMutation = useDeletePattern()

  // Profile form
  const profileForm = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      nome: user?.nome || '',
      email: user?.email || '',
      whatsapp: user?.whatsapp || '',
    },
  })

  // Password form
  const passwordForm = useForm<ChangePasswordFormData>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: {
      senhaAtual: '',
      senhaNova: '',
      confirmarSenha: '',
    },
  })

  const onProfileSubmit = (data: ProfileFormData) => {
    updateProfileMutation.mutate(data)
  }

  const onPasswordSubmit = (data: ChangePasswordFormData) => {
    changePasswordMutation.mutate(
      { senhaAtual: data.senhaAtual, senhaNova: data.senhaNova },
      { onSuccess: () => passwordForm.reset() }
    )
  }

  // Custom categories
  const customCategories = categories?.filter((c) => !c.padrao) || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Configurações</h1>
        <p className="text-muted-foreground">
          Gerencie suas preferências e configurações da conta
        </p>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="perfil" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2 lg:grid-cols-5">
          <TabsTrigger value="perfil" className="flex items-center gap-2">
            <User className="h-4 w-4" />
            <span className="hidden sm:inline">Perfil</span>
          </TabsTrigger>
          <TabsTrigger value="categorias" className="flex items-center gap-2">
            <Palette className="h-4 w-4" />
            <span className="hidden sm:inline">Categorias</span>
          </TabsTrigger>
          <TabsTrigger value="assistente" className="flex items-center gap-2">
            <Bot className="h-4 w-4" />
            <span className="hidden sm:inline">Assistente IA</span>
          </TabsTrigger>
          <TabsTrigger value="alertas" className="flex items-center gap-2">
            <Bell className="h-4 w-4" />
            <span className="hidden sm:inline">Alertas</span>
          </TabsTrigger>
          <TabsTrigger value="familia" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            <span className="hidden sm:inline">Família</span>
          </TabsTrigger>
        </TabsList>

        {/* PERFIL TAB */}
        <TabsContent value="perfil" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Informações Pessoais</CardTitle>
              <CardDescription>Atualize seus dados pessoais</CardDescription>
            </CardHeader>
            <CardContent>
              <Form {...profileForm}>
                <form onSubmit={profileForm.handleSubmit(onProfileSubmit)} className="space-y-4">
                  <FormField
                    control={profileForm.control}
                    name="nome"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Nome</FormLabel>
                        <FormControl>
                          <Input {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={profileForm.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Email</FormLabel>
                        <FormControl>
                          <Input type="email" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={profileForm.control}
                    name="whatsapp"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>WhatsApp</FormLabel>
                        <FormControl>
                          <Input type="tel" placeholder="11999998888" {...field} />
                        </FormControl>
                        <FormDescription>
                          Usado para integração com o bot de registro
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <Button type="submit" disabled={updateProfileMutation.isPending}>
                    {updateProfileMutation.isPending ? (
                      <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Salvando...</>
                    ) : (
                      <><Save className="mr-2 h-4 w-4" /> Salvar alterações</>
                    )}
                  </Button>
                </form>
              </Form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Alterar Senha</CardTitle>
              <CardDescription>Atualize sua senha de acesso</CardDescription>
            </CardHeader>
            <CardContent>
              <Form {...passwordForm}>
                <form onSubmit={passwordForm.handleSubmit(onPasswordSubmit)} className="space-y-4">
                  <FormField
                    control={passwordForm.control}
                    name="senhaAtual"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Senha atual</FormLabel>
                        <FormControl>
                          <Input type="password" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField
                      control={passwordForm.control}
                      name="senhaNova"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Nova senha</FormLabel>
                          <FormControl>
                            <Input type="password" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={passwordForm.control}
                      name="confirmarSenha"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Confirmar nova senha</FormLabel>
                          <FormControl>
                            <Input type="password" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                  <Button type="submit" disabled={changePasswordMutation.isPending}>
                    {changePasswordMutation.isPending ? (
                      <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Alterando...</>
                    ) : (
                      'Alterar senha'
                    )}
                  </Button>
                </form>
              </Form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* CATEGORIAS TAB */}
        <TabsContent value="categorias">
          <Card>
            <CardHeader>
              <CardTitle>Categorias Personalizadas</CardTitle>
              <CardDescription>Crie categorias para organizar suas transações</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {loadingCats ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
                </div>
              ) : customCategories.length > 0 ? (
                <div className="space-y-2">
                  {customCategories.map((cat) => (
                    <div
                      key={cat.id}
                      className="flex items-center justify-between p-3 rounded-lg border"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="w-8 h-8 rounded-full flex items-center justify-center text-lg"
                          style={{ backgroundColor: cat.cor + '20' }}
                        >
                          {cat.icone}
                        </div>
                        <div>
                          <span className="font-medium">{cat.nome}</span>
                          <Badge variant="outline" className="ml-2 text-xs">
                            {cat.tipo === 'receita' ? 'Receita' : 'Despesa'}
                          </Badge>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        onClick={() => setDeleteCategory(cat)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center py-8 text-muted-foreground">
                  Nenhuma categoria personalizada criada
                </p>
              )}
              <Button variant="outline" className="w-full">
                <Plus className="h-4 w-4 mr-2" /> Nova categoria
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ASSISTENTE IA TAB */}
        <TabsContent value="assistente" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Personalidade do Assistente</CardTitle>
              <CardDescription>Configure como o assistente deve se comunicar com você</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {loadingPrefs ? (
                <Skeleton className="h-20 w-full" />
              ) : (
                <div className="grid gap-3">
                  {personalityOptions.map((option) => (
                    <div
                      key={option.value}
                      className={`flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-colors ${
                        preferences?.personalidade === option.value
                          ? 'border-primary bg-primary/5'
                          : 'hover:bg-secondary/50'
                      }`}
                      onClick={() => updatePrefsMutation.mutate({ personalidade: option.value as any })}
                    >
                      <div>
                        <p className="font-medium">{option.label}</p>
                        <p className="text-sm text-muted-foreground">{option.description}</p>
                      </div>
                      {preferences?.personalidade === option.value && (
                        <Badge>Ativo</Badge>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Padrões Aprendidos</CardTitle>
              <CardDescription>A IA aprende suas preferências automaticamente</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingPatterns ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
                </div>
              ) : patterns && patterns.length > 0 ? (
                <div className="space-y-2">
                  {patterns.map((pattern) => (
                    <div
                      key={pattern.id}
                      className="flex items-center justify-between p-2 rounded border text-sm"
                    >
                      <div>
                        <span className="font-medium">{pattern.palavras_chave}</span>
                        <span className="mx-2">→</span>
                        <span className="text-muted-foreground">
                          {pattern.categoria?.icone} {pattern.categoria?.nome}
                        </span>
                        <Badge variant="secondary" className="ml-2 text-xs">
                          {Math.round(pattern.confianca * 100)}%
                        </Badge>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => setDeletePatternItem(pattern)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center py-8 text-muted-foreground">
                  Nenhum padrão aprendido ainda
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ALERTAS TAB */}
        <TabsContent value="alertas">
          <Card>
            <CardHeader>
              <CardTitle>Configurações de Alertas</CardTitle>
              <CardDescription>Defina quando você quer ser notificado</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {loadingPrefs ? (
                <div className="space-y-4">
                  {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Alertar vencimentos</Label>
                      <p className="text-sm text-muted-foreground">
                        Receba alertas de contas próximas do vencimento
                      </p>
                    </div>
                    <Switch
                      checked={preferences?.alertar_vencimentos}
                      onCheckedChange={(checked) =>
                        updatePrefsMutation.mutate({ alertar_vencimentos: checked })
                      }
                    />
                  </div>

                  {preferences?.alertar_vencimentos && (
                    <div className="flex items-center gap-4 pl-4 border-l-2">
                      <Label>Dias antes</Label>
                      <Select
                        value={preferences?.dias_antes_vencimento?.toString()}
                        onValueChange={(value) =>
                          updatePrefsMutation.mutate({ dias_antes_vencimento: Number(value) })
                        }
                      >
                        <SelectTrigger className="w-24">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {[1, 2, 3, 5, 7, 10].map((d) => (
                            <SelectItem key={d} value={d.toString()}>
                              {d} {d === 1 ? 'dia' : 'dias'}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Alertar gastos anômalos</Label>
                      <p className="text-sm text-muted-foreground">
                        Avise quando gastar muito acima da média
                      </p>
                    </div>
                    <Switch
                      checked={preferences?.alertar_gastos_anomalos}
                      onCheckedChange={(checked) =>
                        updatePrefsMutation.mutate({ alertar_gastos_anomalos: checked })
                      }
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Resumo diário</Label>
                      <p className="text-sm text-muted-foreground">
                        Receba um resumo diário das suas finanças
                      </p>
                    </div>
                    <Switch
                      checked={preferences?.resumo_diario}
                      onCheckedChange={(checked) =>
                        updatePrefsMutation.mutate({ resumo_diario: checked })
                      }
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Resumo semanal</Label>
                      <p className="text-sm text-muted-foreground">
                        Receba um resumo semanal toda segunda-feira
                      </p>
                    </div>
                    <Switch
                      checked={preferences?.resumo_semanal}
                      onCheckedChange={(checked) =>
                        updatePrefsMutation.mutate({ resumo_semanal: checked })
                      }
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Resumo mensal</Label>
                      <p className="text-sm text-muted-foreground">
                        Receba um resumo mensal no primeiro dia do mês
                      </p>
                    </div>
                    <Switch
                      checked={preferences?.resumo_mensal}
                      onCheckedChange={(checked) =>
                        updatePrefsMutation.mutate({ resumo_mensal: checked })
                      }
                    />
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* FAMÍLIA TAB */}
        <TabsContent value="familia">
          <Card>
            <CardHeader>
              <CardTitle>Membros da Família</CardTitle>
              <CardDescription>
                Membros que podem registrar transações via WhatsApp
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {loadingFamily ? (
                <div className="space-y-2">
                  {[1, 2].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
                </div>
              ) : familyMembers && familyMembers.length > 0 ? (
                <div className="space-y-2">
                  {familyMembers.map((member) => (
                    <div
                      key={member.id}
                      className="flex items-center justify-between p-3 rounded-lg border"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-medium">
                          {member.nome.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium">{member.nome}</p>
                          <p className="text-sm text-muted-foreground">{member.whatsapp}</p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        onClick={() => setDeleteMember(member)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center py-8 text-muted-foreground">
                  Nenhum membro adicionado
                </p>
              )}
              <Button variant="outline" className="w-full">
                <Plus className="h-4 w-4 mr-2" /> Adicionar membro
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Delete Category Dialog */}
      <AlertDialog open={!!deleteCategory} onOpenChange={(open) => !open && setDeleteCategory(undefined)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir categoria?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação não pode ser desfeita. Transações desta categoria não serão afetadas.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleteCategory) {
                  deleteCategoryMutation.mutate(deleteCategory.id, {
                    onSuccess: () => setDeleteCategory(undefined),
                  })
                }
              }}
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Member Dialog */}
      <AlertDialog open={!!deleteMember} onOpenChange={(open) => !open && setDeleteMember(undefined)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remover membro?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta pessoa não poderá mais registrar transações via WhatsApp.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleteMember) {
                  deleteFamilyMutation.mutate(deleteMember.id, {
                    onSuccess: () => setDeleteMember(undefined),
                  })
                }
              }}
            >
              Remover
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Pattern Dialog */}
      <AlertDialog open={!!deletePattern} onOpenChange={(open) => !open && setDeletePatternItem(undefined)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir padrão?</AlertDialogTitle>
            <AlertDialogDescription>
              A IA esquecerá este padrão aprendido.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deletePattern) {
                  deletePatternMutation.mutate(deletePattern.id, {
                    onSuccess: () => setDeletePatternItem(undefined),
                  })
                }
              }}
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
